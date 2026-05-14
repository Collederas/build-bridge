from __future__ import annotations

from build_bridge.models import AppState, Project


def get_app_state(session) -> AppState:
    state = session.query(AppState).order_by(AppState.id.asc()).first()
    if state:
        return state

    state = AppState()
    first_project = session.query(Project).order_by(Project.id.asc()).first()
    if first_project:
        state.active_project_id = first_project.id
    session.add(state)
    session.flush()
    return state


def get_active_project(session) -> Project | None:
    state = get_app_state(session)
    if state.active_project_id:
        project = session.get(Project, state.active_project_id)
        if project:
            return project

    project = session.query(Project).order_by(Project.id.asc()).first()
    state.active_project_id = project.id if project else None
    session.flush()
    return project


def set_active_project(session, project_id: int | None) -> Project | None:
    state = get_app_state(session)
    project = session.get(Project, project_id) if project_id else None
    state.active_project_id = project.id if project else None
    session.add(state)
    session.flush()
    return project

