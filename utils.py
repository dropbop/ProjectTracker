import os
from flask import session

def inject_css_files(STATIC_FOLDER):
    """Injects a list of CSS files into the template context."""
    css_files = [f for f in os.listdir(STATIC_FOLDER) if f.endswith('.css')]
    return {'css_files': css_files}

def set_style(request, STATIC_FOLDER):
    """Sets the selected stylesheet in the session."""
    selected_style = request.form.get('selected_style')
    if selected_style in [f for f in os.listdir(STATIC_FOLDER) if f.endswith('.css')]:
        session['current_style'] = selected_style
    return selected_style