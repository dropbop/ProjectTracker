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

# --- Anki Imports ---
# Assuming these functions exist in an 'anki.py' file or similar module
try:
    from anki import (
        load_anki_data, save_anki_data, create_card, get_card, update_card,
        delete_card, get_due_cards, process_card_review
    )
    anki_enabled = True
except ImportError:
    print("WARNING: Anki module not found. Anki features will be disabled.")
    anki_enabled = False
    # Define dummy functions if anki module is missing to prevent NameErrors
    def load_anki_data(): return {"cards": []}
    def save_anki_data(data): pass
    def create_card(f, b, r): pass
    def get_card(id): return None
    def update_card(id, f, b, r): pass
    def delete_card(id): pass
    def get_due_cards(): return []
    def process_card_review(id, r): pass
# --- End Anki Imports ---


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

# --- Project Management Routes ---

@app.route("/add_project", methods=["GET", "POST"])
def add_project():
    """Displays the form to add a new project and handles project creation."""
    if request.method == "POST":
        title = request.form["title"]
        description = request.form.get("description", "")
        start_date = request.form["start_date"]
        target_completion_date = request.form.get("target_completion_date")
        status = request.form.get("status", "active")
        create_project(title, description, start_date, target_completion_date, status)
        return redirect(url_for("list_projects_by_category", category=status))

    return render_template("add_project.html")


@app.route("/project/<project_id>")
def view_project(project_id):
    """Displays the details of a specific project."""
    project = get_project(project_id, task_status='active')
    if project:
        sort_by = request.args.get('sort_by', 'due_date')
        order = request.args.get('order', 'asc')
        selected_task_statuses = request.args.getlist('task_status')

        # Sort tasks based on parameters
        if sort_by == 'due_date':
            project['tasks'].sort(key=lambda x: x.get('target_completion_date', '') or '9999-12-31', reverse=(order == 'desc'))

        # If other statuses are selected, override the default filtering
        if selected_task_statuses:
            # Reload project data to get *all* tasks before filtering
            all_project_tasks = get_project(project_id)['tasks']
            project['tasks'] = [task for task in all_project_tasks if task['status'] in selected_task_statuses]
            # Re-sort after filtering if needed
            if sort_by == 'due_date':
                project['tasks'].sort(key=lambda x: x.get('target_completion_date', '') or '9999-12-31', reverse=(order == 'desc'))

        else:
            selected_task_statuses = ['active'] # Set default for template rendering

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


@app.route("/", defaults={"category": "active"}) # Make project list the default home page
@app.route("/projects", defaults={"category": "active"})
@app.route("/projects/<category>")
def list_projects_by_category(category):
    """Lists projects, optionally filtered by category."""
    valid_categories = ["active", "on hold", "complete", "archived", "ongoing"]
    if category not in valid_categories:
        return redirect(url_for("list_projects_by_category", category="active"))

    projects = get_projects_by_category(category)

    sort_by = request.args.get('sort_by', 'next_task_due_date')
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
        # Retrieve existing timestamps to preserve them
        existing_updates_map = {update['id']: update['timestamp'] for update in project.get('updates', [])}
        new_updates = []
        for update_id, update_text in zip(update_ids, update_texts):
            timestamp = existing_updates_map.get(update_id, datetime.now().isoformat()) # Keep old timestamp or use now if somehow missing
            new_updates.append({
                'id': update_id,
                'timestamp': timestamp,
                'description': update_text
            })

        update_project(project_id, title, description, status, start_date, target_completion_date,
                       actual_completion_date, new_updates)
        # Redirect back to the view page, preserving the category if possible
        # It's simpler to just redirect to the project view, as category might change
        return redirect(url_for("view_project", project_id=project_id))

    else:
        # Sorting tasks for display within the edit form
        tasks = project.get('tasks', [])
        if sort_by == 'start_date':
            tasks.sort(key=lambda x: x.get('start_date', '') or '9999-12-31', reverse=(order == 'desc'))
        elif sort_by == 'status':
            status_order = {'active': 0, 'on hold': 1, 'complete': 2, 'archived': 3, 'ongoing': 4}
            tasks.sort(key=lambda x: status_order.get(x.get('status'), 999), reverse=(order == 'desc'))
        project['tasks'] = tasks # Update the project dict with sorted tasks

        return render_template('edit_project.html', project=project, sort_by=sort_by, order=order,
                               show_delete_buttons=True)


@app.route("/edit_task/<project_id>/<task_id>", methods=["GET", "POST"])
def edit_task(project_id, task_id):
    """Displays the form to edit a specific task and handles updating the task."""
    project = get_project(project_id)
    if not project:
        abort(404)

    task = next((t for t in project.get('tasks', []) if t['id'] == task_id), None)
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
    selected_project_statuses = request.args.getlist('project_status') or ['active', 'ongoing']
    selected_task_statuses = request.args.getlist('task_status') or ['active']

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
        # Redirect back to the edit page after adding an update
        return redirect(url_for("edit_project", project_id=project_id))
    else:
        abort(404)


@app.route("/project/<project_id>/delete_update/<update_id>", methods=["POST"])
def delete_update(project_id, update_id):
    """Deletes the specified update from the project."""
    project = get_project(project_id)
    if project:
        delete_project_update(project_id, update_id)
         # Redirect back to the edit page after deleting an update
        return redirect(url_for("edit_project", project_id=project_id))
    else:
        abort(404)


@app.route("/calendar")
def productivity_calendar():
    """Displays productivity heatmap calendar"""
    try:
        data = load_data()
        completion_dates = []

        # Get all completion dates from projects and tasks
        for project in data.get('projects', []):
            if project.get('actual_completion_date'):
                completion_dates.append(project['actual_completion_date'])
            for task in project.get('tasks', []):
                if task.get('actual_completion_date'):
                    completion_dates.append(task['actual_completion_date'])

        # Create date counts dictionary
        date_counts = {}
        for date_str in completion_dates:
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
                date_counts[date] = date_counts.get(date, 0) + 1
            except (ValueError, TypeError):
                print(f"Warning: Skipping invalid date format in calendar: {date_str}")
                continue # Skip invalid dates

        # Generate calendar dates (53 weeks)
        today = datetime.today().date()
        num_weeks = 53
        total_days = num_weeks * 7
        start_date = today - timedelta(days=total_days - 1)

        calendar_dates = [start_date + timedelta(days=i) for i in range(total_days)]

        if not calendar_dates: # Should not happen with the logic above, but defensive check
             calendar_dates = [today]

    except Exception as e:
        print(f"Error generating calendar data: {e}")
        # Provide defaults in case of error loading data or processing dates
        date_counts = {}
        today = datetime.today().date()
        num_weeks = 53
        total_days = num_weeks * 7
        start_date = today - timedelta(days=total_days - 1)
        calendar_dates = [start_date + timedelta(days=i) for i in range(total_days)]


    return render_template("calendar.html",
                           date_counts=date_counts,
                           calendar_dates=calendar_dates,
                           today=today)

# --- End Project Management Routes ---


# --- Anki Flashcard Routes ---

if anki_enabled:
    @app.route("/anki")
    def anki_review():
        """Shows flashcards that are due for review."""
        try:
            due_cards = get_due_cards()
            return render_template("anki.html", due_cards=due_cards)
        except Exception as e:
            print(f"Error getting due Anki cards: {e}")
            # Handle error gracefully, maybe show an error message
            return render_template("anki.html", due_cards=[], error="Could not load due cards.")


    @app.route("/anki/review/<card_id>", methods=["POST"])
    def review_card(card_id):
        """Processes a flashcard review."""
        try:
            rating = int(request.form["rating"])
            process_card_review(card_id, rating)
            return redirect(url_for("anki_review"))
        except ValueError:
            # Handle case where rating is not an integer
            return redirect(url_for("anki_review")) # Or show an error
        except Exception as e:
            print(f"Error processing Anki card review for {card_id}: {e}")
            return redirect(url_for("anki_review")) # Redirect back on error


    @app.route("/anki/manage")
    def manage_cards():
        """Lists all flashcards for management."""
        try:
            # Make sure load_anki_data returns a dict with a 'cards' key
            data = load_anki_data()
            cards = data.get("cards", [])
            return render_template("edit_anki.html", cards=cards, mode='list') # Add mode for template logic
        except Exception as e:
            print(f"Error loading Anki data for management: {e}")
            return render_template("edit_anki.html", cards=[], mode='list', error="Could not load card data.")


    @app.route("/anki/add", methods=["GET", "POST"])
    def add_card():
        """Adds a new flashcard."""
        if request.method == "POST":
            try:
                front = request.form["front"]
                back = request.form["back"]
                # Checkbox value is only present if checked
                reverse = "reverse" in request.form
                create_card(front, back, reverse)
                return redirect(url_for("manage_cards"))
            except Exception as e:
                print(f"Error adding Anki card: {e}")
                # Optionally, pass error back to the template
                return render_template("edit_anki.html", mode='add', error="Failed to add card.") # Add mode
        # For GET request, show the add form section
        return render_template("edit_anki.html", mode='add') # Add mode


    @app.route("/anki/edit/<card_id>", methods=["GET", "POST"])
    def edit_card(card_id):
        """Edits an existing flashcard."""
        try:
            card = get_card(card_id)
            if not card:
                abort(404) # Card not found

            if request.method == "POST":
                front = request.form["front"]
                back = request.form["back"]
                reverse = "reverse" in request.form
                update_card(card_id, front, back, reverse)
                return redirect(url_for("manage_cards"))

            # For GET request, show the edit form section populated with card data
            return render_template("edit_anki.html", card=card, mode='edit') # Add mode

        except Exception as e:
            print(f"Error editing Anki card {card_id}: {e}")
            # Handle error, maybe redirect back to manage page with an error flash
            return redirect(url_for("manage_cards"))


    @app.route("/anki/delete/<card_id>", methods=["POST"])
    def delete_card_route(card_id):
        """Deletes a flashcard."""
        try:
            delete_card(card_id)
            return redirect(url_for("manage_cards"))
        except Exception as e:
            print(f"Error deleting Anki card {card_id}: {e}")
            # Handle error, maybe redirect back to manage page with an error flash
            return redirect(url_for("manage_cards"))

else:
    # Optional: Add routes that inform the user Anki is disabled if they try to access /anki/*
    @app.route("/anki")
    @app.route("/anki/manage")
    @app.route("/anki/add")
    @app.route("/anki/edit/<card_id>")
    def anki_disabled(*args, **kwargs):
        # You could render a simple template or return a message
        return "Anki functionality is currently disabled because the 'anki' module could not be found.", 404


# --- End Anki Flashcard Routes ---


if __name__ == "__main__":
    # Ensure data files exist (optional, depends on data_handler implementation)
    # Example: if data_handler.DATA_FILE and not os.path.exists(data_handler.DATA_FILE):
    #     data_handler.save_data({"projects": [], "tasks": []}) # Create empty file
    # Example: if anki_enabled and anki.ANKI_DATA_FILE and not os.path.exists(anki.ANKI_DATA_FILE):
    #     anki.save_anki_data({"cards": []}) # Create empty Anki file

    app.run(debug=True)