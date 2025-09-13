import html
from .utils import sanitize_for_css_class, format_timestamp

def generate_epub_list_html(epub_files, story_id_sanitized):
    if not epub_files:
        return "<p class=\"no-items\">No EPUB files found.</p>"

    EPUB_DISPLAY_THRESHOLD = 3
    total_epubs = len(epub_files)
    output_html = "<ul class=\"file-list\">"

    for i, file_data in enumerate(epub_files):
        item_html = f"<li><a href=\"file:///{html.escape(file_data['path'])}\" title=\"{html.escape(file_data['path'])}\">{html.escape(file_data['name'])}</a></li>"
        if i < EPUB_DISPLAY_THRESHOLD:
            output_html += item_html
        else:
            if i == EPUB_DISPLAY_THRESHOLD: # Start of hidden items
                output_html += f"</ul><div id=\"more-epubs-{story_id_sanitized}\" style=\"display:none;\"><ul class=\"file-list\">"
            output_html += item_html
            if i == total_epubs - 1: # End of hidden items
                output_html += "</ul></div>"

    if total_epubs > EPUB_DISPLAY_THRESHOLD:
        if total_epubs - 1 < EPUB_DISPLAY_THRESHOLD : # only one hidden item, close first ul
             output_html += "</ul>" # close the main list if hidden part was not created
        # Add the button/link to toggle visibility
        remaining_count = total_epubs - EPUB_DISPLAY_THRESHOLD
        button_text = f"Show all {total_epubs} EPUBs" # Initial text shows total
        output_html += f"<button type=\"button\" class=\"toggle-epubs-btn\" onclick=\"toggleExtraEpubs('{story_id_sanitized}', this, {total_epubs}, {EPUB_DISPLAY_THRESHOLD})\">{button_text}</button>"
    else:
        output_html += "</ul>" # Close the main list if no hidden part

    return output_html

def generate_backup_files_html(backup_files_list, format_timestamp_func):
    if not backup_files_list:
        return "<p class=\"no-items\">No backup file details.</p>"
    items = ""
    for bf in backup_files_list:
        ts = format_timestamp_func(bf.get('last_backed_up_timestamp')) or 'N/A'
        local_path_display = html.escape(bf.get('local_path', 'N/A'))
        cloud_file_name_display = html.escape(bf.get('cloud_file_name', 'N/A'))
        status_display = html.escape(bf.get('status', 'N/A'))
        items += f"<li>{local_path_display} ({cloud_file_name_display}): {status_display} - Last backed up: {ts}</li>"
    return f"<ul class=\"file-list\">{items}</ul>"

def get_html_skeleton(title_text, css_styles, body_content, js_script=""):
    return f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <meta name="theme-color" content="#6750a4">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <meta name="apple-mobile-web-app-title" content="Webnovel Archive">
    <meta name="description" content="Webnovel Archive Report - View your archived webnovels">
    <meta name="format-detection" content="telephone=no">
    <title>{html.escape(title_text)}</title>

    <!-- Preload critical resources -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">

    <!-- Favicon -->
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📚</text></svg>">

    <!-- Web App Manifest -->
    <link rel="manifest" href="manifest.json">

    <style>
        {css_styles}
    </style>
</head>
<body>
    {body_content}

    <div id="storyDetailModal" class="modal">
        <div class="modal-content">
            <button class="modal-close-btn" aria-label="Close modal">&times;</button>
            <div id="modalBodyContent">
                <!-- Story details will be injected here by JavaScript -->
            </div>
        </div>
    </div>

    <script>
        {js_script}
    </script>
</body>
</html>
'''

def generate_story_card_html(story_data, format_timestamp_func):
    title = html.escape(story_data.get('title') or 'Untitled')
    author = html.escape(story_data.get('author') or 'Unknown Author')
    story_url = html.escape(story_data.get('story_url') or '#')
    cover_image_url = html.escape(story_data.get('cover_image_url') or 'https://via.placeholder.com/150x220.png?text=No+Cover')
    synopsis = html.escape(story_data.get('synopsis') or 'No synopsis available.')
    progress_text = html.escape(story_data.get('progress_text') or 'N/A')
    status_display_text = html.escape(story_data.get('status') or 'N/A')
    epub_gen_ts = html.escape(story_data.get('epub_generation_timestamp') or 'N/A')

    epub_files_list = story_data.get('epub_files', [])
    story_id_for_epub_toggle = sanitize_for_css_class(story_data.get('story_id') or '')
    story_id_display = html.escape(story_data.get('story_id') or 'N/A')
    backup_summary_display_text = html.escape(story_data.get('backup_status_summary') or 'N/A')
    backup_service = html.escape(story_data.get('backup_service') or 'N/A')
    backup_last_success_ts = html.escape(story_data.get('formatted_last_successful_backup_ts') or 'N/A')
    backup_files_detail_list = story_data.get('backup_files_status', [])
    last_updated = html.escape(story_data.get('formatted_last_updated_ts') or 'N/A')
    chapters_for_report = story_data.get('chapters_for_report', [])

    data_title = html.escape(story_data.get('title') or '')
    data_author = html.escape(story_data.get('author') or '')
    data_status = html.escape(story_data.get('status') or '')
    data_last_updated = html.escape(
        story_data.get('last_download_timestamp') or
        story_data.get('last_updated_timestamp') or
        story_data.get('last_archived_timestamp') or
        story_data.get('epub_generation_timestamp_raw') or
        ''
    )
    data_progress = html.escape(str(story_data.get('progress_percentage', 0)))

    status_class = sanitize_for_css_class(story_data.get('status'))
    backup_summary_class = sanitize_for_css_class(story_data.get('backup_status_summary'))

    epub_list_html = generate_epub_list_html(epub_files_list, story_id_for_epub_toggle)
    story_id_for_modal = story_id_for_epub_toggle

    chapters_html = ""
    if chapters_for_report:
        chapter_items = []
        for chapter in chapters_for_report:
            title = html.escape(chapter.get('title', 'Untitled Chapter'))
            url = html.escape(chapter.get('url', '#'))
            status = chapter.get('status', 'active')
            downloaded = chapter.get('downloaded', False)

            # Determine status class and icon
            status_class = "archived" if status == 'archived' else ("downloaded" if downloaded else "not-downloaded")
            status_icon = "📚" if status == 'archived' else ("✅" if downloaded else "⏳")
            status_text = "Archived" if status == 'archived' else ("Downloaded" if downloaded else "Not Downloaded")

            chapter_content = f'<span class="chapter-title">{title}</span>'
            if url and url != '#':
                chapter_content = f'<a href="{url}" target="_blank" rel="noopener">{title}</a>'

            chapter_items.append(f'''
                <li>
                    {chapter_content}
                    <span class="chapter-status {status_class}">
                        {status_icon} {status_text}
                    </span>
                </li>
            ''')

        if chapter_items:
            chapters_html = f'''
            <p class="section-title">Chapters ({len(chapters_for_report)} total):</p>
            <ul class="file-list chapter-list">{' '.join(chapter_items)}</ul>
            '''
        else:
            chapters_html = '<p class="section-title">Chapters:</p><p class="no-items">No chapter details available.</p>'
    else:
        chapters_html = '<p class="section-title">Chapters:</p><p class="no-items">No chapter details available.</p>'

    # Calculate progress percentage for progress bar
    progress_percentage = story_data.get('progress_percentage', 0)

    card_html = f'''
    <div class="story-card" data-title="{data_title}" data-author="{data_author}" data-status="{data_status}" data-last-updated="{data_last_updated}" data-progress="{data_progress}">
        <div class="story-card-summary">
            <div class="story-cover">
                <img src="{cover_image_url}" alt="Cover for {title}" loading="lazy">
            </div>
            <div class="story-summary-info">
                <h2><a href="{story_url}" target="_blank" rel="noopener">{title}</a></h2>
                <p><strong>Author:</strong> {author}</p>
                <p><strong>Story ID:</strong> {story_id_display}</p>

                <div class="progress-container">
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {progress_percentage}%"></div>
                    </div>
                    <div class="progress-text">{progress_text}</div>
                </div>

                <div class="story-meta">
                    <div class="story-meta-item">
                        <span class="badge status-{status_class}">{status_display_text}</span>
                    </div>
                    <div class="story-meta-item">
                        <span>📅 {last_updated}</span>
                    </div>
                </div>

                <button class="view-details-btn" data-story-id="{story_id_for_modal}">
                    <span>📖</span>
                    View Details
                </button>
            </div>
        </div>
        <div class="story-card-modal-content" style="display: none;">
            <div class="modal-header">
                <h1>{title}</h1>
                <p class="modal-subtitle">by {author}</p>
            </div>

            <p class="section-title">📝 Synopsis</p>
            <div class="synopsis" onclick="toggleSynopsis(this)">{synopsis}</div>
            <span class="synopsis-toggle" onclick="toggleSynopsis(this.previousElementSibling)">(Read more)</span>

            <p class="section-title">📊 Download Progress</p>
            <div class="progress-container">
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {progress_percentage}%"></div>
                </div>
                <div class="progress-text">{progress_text}</div>
            </div>
            <p><strong>Story Status:</strong> <span class="badge status-{status_class}">{status_display_text}</span></p>

            {chapters_html}

            <p class="section-title">📚 Local EPUBs</p>
            <p><em>Generated: {epub_gen_ts}</em></p>
            {epub_list_html}

            <p class="section-title">☁️ Cloud Backup</p>
            <p><strong>Status:</strong> <span class="badge backup-{backup_summary_class}">{backup_summary_display_text}</span>
               <br><em>Service: {backup_service}</em>
            </p>
            <p><strong>Last Successful Backup:</strong> {backup_last_success_ts}</p>
            {generate_backup_files_html(backup_files_detail_list, format_timestamp)}

            <p class="section-title">🕒 Last Local Update</p>
            <p>{last_updated}</p>
        </div>
    </div>
    '''
    return card_html
