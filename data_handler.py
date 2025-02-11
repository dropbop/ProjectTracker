import json
import os
import uuid
from datetime import datetime

DATA_FILE = "project_data.json"  # Moved to a constant

def load_data():
    """Loads project data from the JSON file."""
    if not os.path.exists(DATA_FILE):
        return {"projects": []}
    try:
        with open(DATA_FILE, 'r') as file:
            return json.load(file)
    except json.JSONDecodeError:
        print(f"Error decoding JSON from {DATA_FILE}. Returning empty project list.")
        return {"projects": []}

def save_data(data):
    """Saves project data to the JSON file."""
    with open(DATA_FILE, 'w') as file:
        json.dump(data, file, indent=4)

def get_project(project_id, task_status='active'):  # Add task_status parameter with 'active' as the default
    """Retrieves a specific project by ID with optional task filtering."""
    data = load_data()
    project = next((p for p in data['projects'] if p['id'] == project_id), None)

    if project and task_status:
        # Filter tasks based on status if provided
        project['tasks'] = [task for task in project['tasks'] if task['status'] == task_status]

    return project

def get_projects_by_category(category):
    """Filters projects based on their status category and adds next_task_due_date."""
    data = load_data()
    projects = []
    for project in data['projects']:
        if project['status'] == category:
            # Get the active tasks for the project, handling missing dates
            active_tasks = [
                task for task in project.get('tasks', [])
                if task['status'] == 'active' and task.get('target_completion_date')
            ]

            # Find the next task due date
            if active_tasks:
                next_task_due_date = min(
                    task['target_completion_date'] for task in active_tasks
                )
            else:
                # Use a far-off date if no active tasks with due dates
                next_task_due_date = '9999-12-31'

            project['next_task_due_date'] = next_task_due_date
            projects.append(project)

    return projects

def create_project(title, description, start_date, target_completion_date, status="active"):  # Add status parameter
    """Creates a new project."""
    data = load_data()
    project_id = uuid.uuid4().hex
    new_project = {
        "id": project_id,
        "title": title,
        "description": description,
        "start_date": start_date,
        "target_completion_date": target_completion_date,
        "actual_completion_date": None,
        "status": status,  # Use the status parameter
        "updates": [],
        "tasks": []
    }
    data["projects"].append(new_project)
    save_data(data)
    return project_id

def update_project(project_id, title, description, status, start_date, target_completion_date, actual_completion_date, updates):
    """Updates an existing project."""
    data = load_data()
    project = next((p for p in data['projects'] if p['id'] == project_id), None)
    if project:
        project["title"] = title
        project["description"] = description
        project["status"] = status
        project["start_date"] = start_date
        project["target_completion_date"] = target_completion_date
        project["actual_completion_date"] = actual_completion_date
        project["updates"] = updates
        save_data(data)

def create_task(project_id, description, additional_info, start_date, target_completion_date, actual_completion_date, status):
    """Creates a new task for a project."""
    data = load_data()
    project = next((p for p in data['projects'] if p['id'] == project_id), None)
    if project:
        task_id = uuid.uuid4().hex
        new_task = {
            "id": task_id,
            "description": description,
            "additional_info": additional_info,
            "start_date": start_date,
            "target_completion_date": target_completion_date,
            "actual_completion_date": actual_completion_date,
            "status": status,
            "updates": []
        }
        project["tasks"].append(new_task)
        save_data(data)
        return task_id

def update_task(project_id, task_id, description, additional_info, status, start_date, target_completion_date, actual_completion_date):
    """Updates an existing task."""
    data = load_data()
    project = next((p for p in data['projects'] if p['id'] == project_id), None)
    if project:
        task = next((t for t in project['tasks'] if t['id'] == task_id), None)
        if task:
            task["description"] = description
            task["additional_info"] = additional_info
            task["status"] = status
            task["start_date"] = start_date
            task["target_completion_date"] = target_completion_date
            task["actual_completion_date"] = actual_completion_date
            save_data(data)

def get_all_tasks(sort_by='due_date', order='asc', selected_project_statuses=None, selected_task_statuses=None):
    """Retrieves all tasks with optional sorting and filtering."""
    data = load_data()
    all_tasks = []
    for project in data['projects']:
        for task in project['tasks']:
            task_data = {
                'project_id': project['id'],
                'project_title': project['title'],
                'project_status': project['status'],
                'task_id': task['id'],
                'description': task['description'],
                'target_completion_date': task.get('target_completion_date'),
                'status': task['status']
            }

            # Apply filtering
            if selected_project_statuses and task_data['project_status'] not in selected_project_statuses:
                continue
            if selected_task_statuses and task_data['status'] not in selected_task_statuses:
                continue

            all_tasks.append(task_data)

    # Apply sorting
    if sort_by == 'due_date':
        all_tasks.sort(key=lambda x: x.get('target_completion_date') or '9999-12-31', reverse=(order == 'desc'))

    return all_tasks

def add_project_update(project_id, update_text):
    """Adds a new update to a project."""
    data = load_data()
    project = next((p for p in data['projects'] if p['id'] == project_id), None)
    if project:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        new_update = {
            'id': uuid.uuid4().hex,
            'timestamp': timestamp,
            'description': update_text
        }
        project['updates'].append(new_update)
        save_data(data)

def delete_project_update(project_id, update_id):
    """Deletes an update from a project."""
    data = load_data()
    project = next((p for p in data['projects'] if p['id'] == project_id), None)
    if project:
        project['updates'] = [u for u in project['updates'] if u['id'] != update_id]
        save_data(data)

def get_completion_data():
    """Returns all completion dates from projects and tasks"""
    data = load_data()
    completions = []

    for project in data['projects']:
        if project['actual_completion_date']:
            completions.append({
                'type': 'project',
                'date': project['actual_completion_date'],
                'title': project['title']
            })
        for task in project['tasks']:
            if task['actual_completion_date']:
                completions.append({
                    'type': 'task',
                    'date': task['actual_completion_date'],
                    'title': task['description']
                })

    return completions