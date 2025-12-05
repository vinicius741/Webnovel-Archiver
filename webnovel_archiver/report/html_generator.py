import html
from .utils import sanitize_for_css_class, format_timestamp

def generate_epub_list_html(epub_files, story_id_sanitized):
    if not epub_files:
        return "<p class=\"text-content\" style=\"font-style: italic;\">No EPUB files found.</p>"

    EPUB_DISPLAY_THRESHOLD = 3
    total_epubs = len(epub_files)
    output_html = "<ul class=\"file-list\">"

    for i, file_data in enumerate(epub_files):
        item_html = f"<li><span>📄 {html.escape(file_data['name'])}</span> <a href=\"file:///{html.escape(file_data['path'])}\" title=\"{html.escape(file_data['path'])}\" class=\"btn-primary\" style=\"font-size: 0.8rem; padding: 4px 10px;\">Open</a></li>"
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
             output_html += "</ul>"
        
        remaining_count = total_epubs - EPUB_DISPLAY_THRESHOLD
        button_text = f"Show all {total_epubs} EPUBs"
        output_html += f"<button type=\"button\" class=\"btn-primary\" style=\"margin-top: 10px; background: transparent; border: 1px solid var(--glass-border); width: 100%;\" onclick=\"toggleExtraEpubs('{story_id_sanitized}', this, {total_epubs}, {EPUB_DISPLAY_THRESHOLD})\">{button_text}</button>"
    else:
        output_html += "</ul>"

    return output_html

def generate_backup_files_html(backup_files_list, format_timestamp_func):
    if not backup_files_list:
        return "<p class=\"text-content\">No backup file details.</p>"
    items = ""
    for bf in backup_files_list:
        ts = format_timestamp_func(bf.get('last_backed_up_timestamp')) or 'N/A'
        local_path_display = html.escape(bf.get('local_path', 'N/A'))
        cloud_file_name_display = html.escape(bf.get('cloud_file_name', 'N/A'))
        status_display = html.escape(bf.get('status', 'N/A'))
        
        # Determine status color
        status_color = "var(--status-info)"
        if "success" in status_display.lower(): status_color = "var(--status-success)"
        elif "fail" in status_display.lower(): status_color = "var(--status-error)"

        items += f"<li><div style='display:flex; flex-direction:column; gap:4px;'><strong>{cloud_file_name_display}</strong><span style='font-size:0.8rem; color:var(--text-muted);'>{local_path_display}</span></div> <span style='color:{status_color}; font-size:0.8rem;'>{status_display} ({ts})</span></li>"
    return f"<ul class=\"file-list\">{items}</ul>"

def get_html_skeleton(title_text, css_styles, body_content, js_script=""):
    return f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <meta name="theme-color" content="#0f0c29">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <title>{html.escape(title_text)}</title>

    <!-- Google Fonts: Outfit for headings, Inter for body -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">

    <!-- Favicon -->
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📚</text></svg>">

    <style>
        {css_styles}
    </style>
</head>
<body>
    {body_content}

    <div id="storyDetailModal" class="modal">
        <div class="modal-content">
            <div class="modal-header-bg">
                <h1 id="modalTitle" style="margin:0; font-family:'Outfit';">Story Title</h1>
                <p id="modalSubtitle" style="margin:4px 0 0; color:var(--text-muted);">by Author</p>
                <button class="modal-close-btn" aria-label="Close modal">&times;</button>
            </div>
            <div id="modalBodyContent" class="modal-body">
                <!-- Story details injected here -->
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
    cover_image_url = html.escape(story_data.get('cover_image_url') or '')
    if not cover_image_url:
        cover_image_url = f"https://via.placeholder.com/150x220.png/302b63/ffffff?text={html.escape(title[:20])}"
    
    synopsis = html.escape(story_data.get('synopsis') or 'No synopsis available.')
    progress_text = html.escape(story_data.get('progress_text') or 'N/A')
    status_display_text = html.escape(story_data.get('status') or 'N/A')
    epub_gen_ts = html.escape(story_data.get('epub_generation_timestamp') or 'N/A')

    epub_files_list = story_data.get('epub_files', [])
    story_id_for_epub_toggle = sanitize_for_css_class(story_data.get('story_id') or '')
    story_id_display = html.escape(story_data.get('story_id') or 'N/A')
    backup_summary = html.escape(story_data.get('backup_status_summary') or 'N/A')
    backup_service = html.escape(story_data.get('backup_service') or 'N/A')
    backup_last_ts = html.escape(story_data.get('formatted_last_successful_backup_ts') or 'N/A')
    backup_files_detail_list = story_data.get('backup_files_status', [])
    last_updated = html.escape(story_data.get('formatted_last_updated_ts') or 'N/A')
    chapters_for_report = story_data.get('chapters_for_report', [])

    # Data attributes for sorting/filtering
    data_title = html.escape(story_data.get('title') or '')
    data_author = html.escape(story_data.get('author') or '')
    data_status = html.escape(story_data.get('status') or '')
    data_last_updated = html.escape(
        story_data.get('last_download_timestamp') or
        story_data.get('last_updated_timestamp') or
        story_data.get('last_archived_timestamp') or
        ''
    )
    data_progress = html.escape(str(story_data.get('progress_percentage', 0)))

    # Classes
    status_class_suffix = sanitize_for_css_class(story_data.get('status')) # e.g. 'ongoing', 'complete'
    
    # Progress
    progress_percentage = story_data.get('progress_percentage', 0)
    
    # EPUB List
    epub_list_html = generate_epub_list_html(epub_files_list, story_id_for_epub_toggle)
    story_id_for_modal = story_id_for_epub_toggle

    # Chapters HTML
    chapters_html = ""
    if chapters_for_report:
        chapter_items = []
        for chapter in chapters_for_report:
            c_title = html.escape(chapter.get('title', 'Untitled'))
            c_url = html.escape(chapter.get('url', '#'))
            c_downloaded = chapter.get('downloaded', False)
            
            badge_class = "downloaded" if c_downloaded else "missing"
            badge_text = "Downloaded" if c_downloaded else "Not Downloaded"

            link_html = f'<a href="{c_url}" target="_blank">{c_title}</a>' if c_url != '#' else c_title
            
            chapter_items.append(f'''
                <li>
                    <span class="chapter-title">{link_html}</span>
                    <span class="chapter-badge {badge_class}">{badge_text}</span>
                </li>
            ''')
        
        chapters_html = f'''
        <div class="modal-section-title">📂 Chapters ({len(chapters_for_report)})</div>
        <ul class="file-list chapter-list" style="max-height: 300px; overflow-y: auto;">
            {''.join(chapter_items)}
        </ul>
        '''
    else:
        chapters_html = '<div class="modal-section-title">📂 Chapters</div><p class="text-content">No chapter details available.</p>'

    # Card HTML
    card_html = f'''
    <div class="story-card" 
         data-title="{data_title}" 
         data-author="{data_author}" 
         data-status="{data_status}" 
         data-last-updated="{data_last_updated}" 
         data-progress="{data_progress}">
        
        <div class="story-header">
            <div class="story-cover">
                <img src="{cover_image_url}" alt="{title}" loading="lazy">
            </div>
            <div class="story-info">
                <h2 class="story-title"><a href="{story_url}" target="_blank">{title}</a></h2>
                <p class="story-author">by {author}</p>
                <div class="badges">
                    <span class="badge status-{status_class_suffix}">{status_display_text}</span>
                    <span class="badge" style="background:rgba(255,255,255,0.05);">ID: {story_id_display}</span>
                </div>
            </div>
        </div>

        <div class="progress-section">
            <div class="progress-text">
                <span>Progress</span>
                <span>{progress_percentage}%</span>
            </div>
            <div class="progress-bar-bg">
                <div class="progress-fill" style="width: {progress_percentage}%"></div>
            </div>
            <div class="progress-text" style="justify-content: flex-end;">
                <span style="font-size: 0.7rem; opacity: 0.7;">Last: {last_updated}</span>
            </div>
        </div>

        <button class="btn-primary view-details-btn" style="margin-top: 15px; justify-content: center; width: 100%;" data-story-id="{story_id_for_modal}">
            View Details
        </button>

        <!-- Hidden Modal Content Data -->
        <div class="story-card-modal-content" style="display: none;">
            <!-- Simple header data for JS to grab -->
            <div class="hidden-header-data" data-title="{title}" data-author="{author}"></div>

            <div class="modal-section-title">📝 Synopsis</div>
            <div class="synopsis" onclick="toggleSynopsis(this)">{synopsis}</div>
            
            <div class="modal-section-title">📊 Progress</div>
            <div class="text-content">
                <p><strong>Status:</strong> <span class="badge status-{status_class_suffix}">{status_display_text}</span> ({progress_text})</p>
                <p><strong>Last Updated:</strong> {last_updated}</p>
            </div>

            {chapters_html}

            <div class="modal-section-title">📚 Local EPUBs</div>
            <div style="margin-bottom:8px; font-size:0.8rem; color:var(--text-muted);">Generated: {epub_gen_ts}</div>
            {epub_list_html}

            <div class="modal-section-title">☁️ Cloud Backup</div>
            <div class="text-content">
                <p><strong>Service:</strong> {backup_service}</p>
                <p><strong>Summary:</strong> {backup_summary}</p>
                <p><strong>Last Success:</strong> {backup_last_ts}</p>
            </div>
            {generate_backup_files_html(backup_files_detail_list, format_timestamp)}
        </div>
    </div>
    '''
    return card_html
