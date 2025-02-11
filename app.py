from flask import Flask, render_template, request, redirect, url_for, abort, session
import os
from operator import itemgetter
from datetime import datetime, timedelta
from data_handler import (
    get_project, get_projects_by_category, create_project, update_project,
    create_task, update_task, get_all_tasks, add_project_update, delete_project_update,
    load_data  # Assuming load_data is in data_handler.py
)
import utils  # Import the utils module

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'your_default_secret_key')

STATIC_FOLDER = os.path.join(app.root_path, 'static')


@app.context_processor
def inject_css_and_static_folder():
    """Injects CSS files and STATIC_FOLDER into the template context."""
    return {**utils.inject_css_files(STATIC_FOLDER), 'STATIC_FOLDER': STATIC_FOLDER}


@app.route('/set_style', methods=['POST'])
def set_style_route():
    """Route to set the selected stylesheet in the session."""
    utils.set_style(request, STATIC_FOLDER)
    return redirect(request.referrer)


@app.route("/add_project", methods=["GET", "POST"])
def add_project():
    """Displays the form to add a new project and handles project creation."""
    if request.method == "POST":
        title = request.form["title"]
        description = request.form.get("description", "")
        start_date = request.form["start_date"]
        target_completion_date = request.form.get("target_completion_date")
        status = request.form.get("status", "active")  # Get status from form, default to "active"
        create_project(title, description, start_date, target_completion_date, status)  # Pass status to create_project
        return redirect(url_for("list_projects_by_category", category=status))  # Redirect to the category of the new project

    return render_template("add_project.html")


@app.route("/project/<project_id>")
def view_project(project_id):
    """Displays the details of a specific project."""
    project = get_project(project_id, task_status='active')  # Filter for 'active' tasks by default
    if project:
        sort_by = request.args.get('sort_by', 'due_date')  # Default sort by due_date
        order = request.args.get('order', 'asc')  # Default order ascending
        selected_task_statuses = request.args.getlist('task_status')

        # Sort tasks based on parameters
        if sort_by == 'due_date':
            project['tasks'].sort(key=lambda x: x.get('target_completion_date', ''), reverse=(order == 'desc'))

        # If other statuses are selected, override the default filtering
        if selected_task_statuses:
            project['tasks'] = [task for task in get_project(project_id)['tasks'] if
                                 task['status'] in selected_task_statuses]
        else:
            selected_task_statuses = ['active']  # set the default selected filter for the template to be active only

        return render_template("project_detail.html", project_id=project_id, project=project, sort_by=sort_by,
                               order=order, selected_task_statuses=selected_task_statuses)
    else:
        abort(404)


@app.route("/add_task/<project_id>", methods=["POST"])
def add_task(project_id):
    """Handles adding a new task to a specific project."""
    project = get_project(project_id)
    if project:
        description = request.form["description"]
        additional_info = request.form.get("additional_info", "")
        start_date = request.form.get("start_date")
        target_completion_date = request.form.get("target_completion_date")
        actual_completion_date = request.form.get("actual_completion_date")
        status = request.form["status"]
        create_task(project_id, description, additional_info, start_date, target_completion_date,
                    actual_completion_date, status)
        return redirect(url_for("view_project", project_id=project_id))
    else:
        abort(404)


@app.route("/projects", defaults={"category": "active"})
@app.route("/projects/<category>")
def list_projects_by_category(category):
    """Lists projects, optionally filtered by category."""
    valid_categories = ["active", "on hold", "complete", "archived", "ongoing"]
    if category not in valid_categories:
        return redirect(url_for("list_projects_by_category", category="active"))

    projects = get_projects_by_category(category)

    sort_by = request.args.get('sort_by', 'next_task_due_date')  # Default to next_task_due_date
    sort_order = request.args.get('order', 'asc')

    if sort_by == 'start_date':
        projects.sort(key=itemgetter('start_date'), reverse=(sort_order == 'desc'))
    elif sort_by == 'target_completion_date':
        projects.sort(key=lambda p: p.get('target_completion_date') or '9999-12-31', reverse=(sort_order == 'desc'))
    elif sort_by == 'next_task_due_date':
        projects.sort(key=lambda p: p.get('next_task_due_date', '9999-12-31'), reverse=(sort_order == 'desc'))

    return render_template("projects.html", projects=projects, current_category=category, categories=valid_categories,
                           sort_by=sort_by, sort_order=sort_order)


@app.route('/project/<project_id>/edit', methods=['GET', 'POST'])
def edit_project(project_id):
    """Displays the form to edit a project and handles updating the project."""
    project = get_project(project_id)
    if not project:
        abort(404)

    sort_by = request.args.get('sort_by', 'start_date')
    order = request.args.get('order', 'asc')

    if request.method == "POST":
        title = request.form["title"]
        description = request.form.get("description", "")
        status = request.form["status"]
        start_date = request.form["start_date"]
        target_completion_date = request.form.get("target_completion_date")
        actual_completion_date = request.form.get("actual_completion_date")

        # Handle updates
        update_ids = request.form.getlist("update_ids[]")
        update_texts = request.form.getlist("update_texts[]")
        update_timestamps = [update['timestamp'] for update in project['updates'] if
                             update['id'] in update_ids]

        new_updates = []
        for update_id, timestamp, update_text in zip(update_ids, update_timestamps, update_texts):
            new_updates.append({
                'id': update_id,
                'timestamp': timestamp,
                'description': update_text
            })

        update_project(project_id, title, description, status, start_date, target_completion_date,
                       actual_completion_date, new_updates)
        return redirect(url_for("view_project", project_id=project_id))
    else:
        if sort_by == 'start_date':
            project["tasks"].sort(key=lambda x: x.get('start_date', ''), reverse=(order == 'desc'))
        elif sort_by == 'status':
            status_order = {'active': 0, 'on hold': 1, 'complete': 2, 'archived': 3, 'ongoing': 4}
            project["tasks"].sort(key=lambda x: status_order.get(x.get('status'), 999), reverse=(order == 'desc'))

        return render_template('edit_project.html', project=project, sort_by=sort_by, order=order,
                               show_delete_buttons=True)


@app.route("/edit_task/<project_id>/<task_id>", methods=["GET", "POST"])
def edit_task(project_id, task_id):
    """Displays the form to edit a specific task and handles updating the task."""
    project = get_project(project_id)
    if not project:
        abort(404)

    task = next((t for t in project['tasks'] if t['id'] == task_id), None)
    if not task:
        abort(404)

    if request.method == "POST":
        description = request.form["description"]
        additional_info = request.form.get("additional_info", "")
        status = request.form["status"]
        start_date = request.form.get("start_date")
        target_completion_date = request.form.get("target_completion_date")
        actual_completion_date = request.form.get("actual_completion_date")
        update_task(project_id, task_id, description, additional_info, status, start_date, target_completion_date,
                    actual_completion_date)
        return redirect(url_for("view_project", project_id=project_id))

    return render_template("edit_task.html", project_id=project_id, task=task)


@app.route('/tasks')
def list_all_tasks():
    """Lists all tasks with optional sorting and filtering."""
    sort_by = request.args.get('sort_by', 'due_date')
    order = request.args.get('order', 'asc')
    selected_project_statuses = request.args.getlist('project_status') or ['active']  # Default to ['active']
    selected_task_statuses = request.args.getlist('task_status') or ['active']  # Default to ['active']

    tasks = get_all_tasks(sort_by, order, selected_project_statuses, selected_task_statuses)

    return render_template('tasks.html', tasks=tasks, sort_by=sort_by, order=order,
                           selected_project_statuses=selected_project_statuses,
                           selected_task_statuses=selected_task_statuses)


@app.route("/project/<project_id>/add_update", methods=["POST"])
def add_update(project_id):
    """Adds a new update to the specified project."""
    project = get_project(project_id)
    if project:
        update_text = request.form.get("update_text")
        if update_text:
            add_project_update(project_id, update_text)
        return redirect(url_for("view_project", project_id=project_id))
    else:
        abort(404)


@app.route("/project/<project_id>/delete_update/<update_id>", methods=["POST"])
def delete_update(project_id, update_id):
    """Deletes the specified update from the project."""
    project = get_project(project_id)
    if project:
        delete_project_update(project_id, update_id)
        return redirect(url_for("view_project", project_id=project_id))
    else:
        abort(404)


@app.route("/calendar")
def productivity_calendar():
    """Displays productivity heatmap calendar"""
    data = load_data()
    completion_dates = []

    # Get all completion dates from projects and tasks
    for project in data['projects']:
        if project['actual_completion_date']:
            completion_dates.append(project['actual_completion_date'])
        for task in project['tasks']:
            if task['actual_completion_date']:
                completion_dates.append(task['actual_completion_date'])

    # Create date counts dictionary
    date_counts = {}
    for date_str in completion_dates:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        date_counts[date] = date_counts.get(date, 0) + 1

    # Generate calendar dates (53 weeks)
    today = datetime.today().date()
    num_weeks = 53
    total_days = num_weeks * 7  # 371 days
    start_date = today - timedelta(days=total_days - 1)  # Start date: today - 370 days

    # Generate list of 371 dates
    calendar_dates = [start_date + timedelta(days=i) for i in range(total_days)]

    if not calendar_dates:
        calendar_dates = [today - timedelta(days=1)]  # Fallback for empty data

    return render_template("calendar.html",
                           date_counts=date_counts,
                           calendar_dates=calendar_dates,
                           today=today)


if __name__ == "__main__":
    app.run(debug=True)