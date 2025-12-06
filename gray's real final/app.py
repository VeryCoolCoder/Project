import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_file
import io
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this in production

# Database configuration
DATABASE = 'journal.db'

# Mood options for the dropdown
MOOD_OPTIONS = ['Happy', 'Sad', 'Neutral', 'Excited', 'Angry']


def init_db():
    """Initialize the database with the journal entries table."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS journal_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            mood TEXT NOT NULL,
            content TEXT NOT NULL,
            date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()
    print("Database initialized successfully.")


def get_db_connection():
    """Create and return a database connection."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


@app.route('/')
def landing():
    """Display the landing page."""
    return render_template('landing.html')


@app.route('/journal')
def index():
    """Display all journal entries on the home page."""
    conn = get_db_connection()

    # Get search parameters
    search_query = request.args.get('search', '')
    date_filter = request.args.get('date', '')

    # Build the query
    query = 'SELECT * FROM journal_entries WHERE 1=1'
    params = []

    if search_query:
        query += ' AND (title LIKE ? OR content LIKE ?)'
        params.extend([f'%{search_query}%', f'%{search_query}%'])

    if date_filter:
        query += ' AND DATE(date_created) = ?'
        params.append(date_filter)

    query += ' ORDER BY date_created DESC'

    entries = conn.execute(query, params).fetchall()

    # Convert entries to a list of dictionaries and convert date strings to datetime objects
    entries_list = []
    for entry in entries:
        entry_dict = dict(entry)
        if entry_dict['date_created']:
            entry_dict['date_created'] = datetime.strptime(entry_dict['date_created'], '%Y-%m-%d %H:%M:%S')
        entries_list.append(entry_dict)

    conn.close()

    return render_template('index.html', entries=entries_list, search_query=search_query, date_filter=date_filter)


@app.route('/add', methods=['GET', 'POST'])
def add_entry():
    """Handle adding a new journal entry."""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        mood = request.form.get('mood', '')
        content = request.form.get('content', '').strip()

        # Validation
        if not title or not mood or not content:
            flash('Please fill in all fields.', 'error')
            return render_template('add_entry.html', moods=MOOD_OPTIONS, title=title, mood=mood, content=content)

        if mood not in MOOD_OPTIONS:
            flash('Invalid mood selected.', 'error')
            return render_template('add_entry.html', moods=MOOD_OPTIONS, title=title, mood=mood, content=content)

        # Insert into database
        conn = get_db_connection()
        conn.execute('INSERT INTO journal_entries (title, mood, content) VALUES (?, ?, ?)',
                     (title, mood, content))
        conn.commit()
        conn.close()

        flash('Journal entry added successfully!', 'success')
        return redirect(url_for('index'))

    return render_template('add_entry.html', moods=MOOD_OPTIONS)


@app.route('/edit/<int:entry_id>', methods=['GET', 'POST'])
def edit_entry(entry_id):
    """Handle editing an existing journal entry."""
    conn = get_db_connection()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        mood = request.form.get('mood', '')
        content = request.form.get('content', '').strip()

        # Validation
        if not title or not mood or not content:
            flash('Please fill in all fields.', 'error')
            entry = {'id': entry_id, 'title': title, 'mood': mood, 'content': content}
            return render_template('edit_entry.html', entry=entry, moods=MOOD_OPTIONS)

        if mood not in MOOD_OPTIONS:
            flash('Invalid mood selected.', 'error')
            entry = {'id': entry_id, 'title': title, 'mood': mood, 'content': content}
            return render_template('edit_entry.html', entry=entry, moods=MOOD_OPTIONS)

        # Update database
        conn.execute('UPDATE journal_entries SET title = ?, mood = ?, content = ? WHERE id = ?',
                     (title, mood, content, entry_id))
        conn.commit()
        conn.close()

        flash('Journal entry updated successfully!', 'success')
        return redirect(url_for('index'))

    # GET request - show edit form
    entry = conn.execute('SELECT * FROM journal_entries WHERE id = ?', (entry_id,)).fetchone()
    conn.close()

    if entry is None:
        flash('Entry not found.', 'error')
        return redirect(url_for('index'))

    return render_template('edit_entry.html', entry=entry, moods=MOOD_OPTIONS)


@app.route('/delete/<int:entry_id>', methods=['POST'])
def delete_entry(entry_id):
    """Handle deleting a journal entry."""
    conn = get_db_connection()
    conn.execute('DELETE FROM journal_entries WHERE id = ?', (entry_id,))
    conn.commit()
    conn.close()

    flash('Journal entry deleted successfully!', 'success')
    return redirect(url_for('index'))


@app.route('/export/<int:entry_id>')
def export_pdf(entry_id):
    """Export a journal entry as a PDF file."""
    conn = get_db_connection()
    entry = conn.execute('SELECT * FROM journal_entries WHERE id = ?', (entry_id,)).fetchone()
    conn.close()

    if entry is None:
        flash('Entry not found.', 'error')
        return redirect(url_for('index'))

    # Create PDF in memory
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=12,
        textColor='#2c3e50'
    )

    mood_style = ParagraphStyle(
        'CustomMood',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=6,
        textColor='#7f8c8d'
    )

    date_style = ParagraphStyle(
        'CustomDate',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=12,
        textColor='#95a5a6'
    )

    content_style = ParagraphStyle(
        'CustomContent',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=12,
        textColor='#34495e'
    )

    # Build PDF content
    story = []

    # Title
    story.append(Paragraph(entry['title'], title_style))
    story.append(Spacer(1, 0.2 * inch))

    # Mood and date
    mood_text = f"Mood: {entry['mood']}"
    date_text = f"Date: {datetime.strptime(entry['date_created'], '%Y-%m-%d %H:%M:%S').strftime('%B %d, %Y at %I:%M %p')}"

    story.append(Paragraph(mood_text, mood_style))
    story.append(Paragraph(date_text, date_style))
    story.append(Spacer(1, 0.3 * inch))

    # Content
    content_paragraphs = entry['content'].split('\n')
    for para in content_paragraphs:
        if para.strip():
            story.append(Paragraph(para.strip(), content_style))
        else:
            story.append(Spacer(1, 0.1 * inch))

    # Build PDF
    doc.build(story)

    # Prepare file for download
    buffer.seek(0)
    filename = f"journal_entry_{entry_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )


@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors."""
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    return render_template('500.html'), 500


if __name__ == '__main__':
    # Initialize the database
    init_db()

    # Run the Flask app
    app.run(debug=True, host='0.0.0.0', port=8080)