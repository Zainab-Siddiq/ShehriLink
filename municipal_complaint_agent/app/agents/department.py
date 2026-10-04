"""
Agent 5 - Department selection.

Known categories use the official category->department table (reliable).
For category 'other' the LLM (if configured) picks from the real department
list; in mock mode it goes to General Services.
"""
from app.data import mock_data
from app.data.mock_database import get_repository
from app.graph.state import ComplaintState, log
from app.llm import run_structured
from app.models.schemas import DepartmentResult

AGENT = "Department Agent"


def select_department_with_rules(category: str, subcategory: str) -> DepartmentResult:
    dept = mock_data.CATEGORY_TO_DEPARTMENT.get(category, "General Services Department")
    human = (subcategory or category).replace("_", " ")
    return DepartmentResult(department=dept,
                            reason=f"The complaint concerns '{human}', which falls under the {dept}.")


def department_node(state: ComplaintState) -> dict:
    category = state.category or "other"
    result, errors = None, []
    departments = get_repository().get_department_names()

    if category == "other":
        system = ("Choose the municipal department responsible for this complaint. "
                  f"Valid departments: {', '.join(departments)}. If unsure choose 'General Services Department'.")
        llm_result, errors = run_structured(AGENT, DepartmentResult, system, f"Complaint: {state.description}")
        if llm_result is not None and llm_result.department in departments:
            result = llm_result
    if result is None:
        result = select_department_with_rules(category, state.subcategory or "")

    entry = log(AGENT, "Selected department", result.department, message="Department selected",
                details={"reason": result.reason})
    return {"department": result.department, "department_reason": result.reason,
            "history": [entry], "errors": errors}
