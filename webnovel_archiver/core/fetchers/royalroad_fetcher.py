from typing import List
import re
from bs4 import BeautifulSoup, Tag

from .base_fetcher import BaseFetcher, StoryMetadata, ChapterInfo

# Placeholder for the example HTML content provided in the issue
# In a real scenario, this would be fetched via an HTTP request
EXAMPLE_STORY_PAGE_HTML = """
<!DOCTYPE html>
<!--[if IE 8]> <html lang="en" class="ie8 no-js"> <![endif]-->
<!--[if IE 9]> <html lang="en" class="ie9 no-js"> <![endif]-->
<!--[if !IE]><!-->
<html lang="en">
<!--<![endif]-->
<head>
    <meta charset="utf-8"/>
    <title>REND | Royal Road</title>
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <meta name="viewport" content="width=device-width, initial-scale=1.0"/>


    <meta name="keywords" content="REND; Temple; free books online; web fiction; free; book; novel; royal road; royalroadl; rrl; legends; fiction">
    <meta name="description" content="Erind Hartwell: dutiful daughter, law student, psychopath, film enthusiast&#x2014;one of these makes her not normal. Was it the psychopath thing? Maybe. Still, (...)">
    <meta property="fb:app_id" content="1585608748421060"/>
    <meta property="og:type" content="books.book">
    <meta property="og:url" content="https://www.royalroad.com/fiction/117255/rend">
    <meta property="og:image" content="https://www.royalroadcdn.com/public/covers-large/117255-rend.jpg?time=1748727569">
    <meta property="og:site_name" content="Royal Road">
    <meta property="og:description" content="Erind Hartwell: dutiful daughter, law student, psychopath, film enthusiast&#x2014;one of these makes her not normal. Was it the psychopath thing? Maybe. Still, she&#x27;s relatively normal in a world where superhumans fight eldritch horrors that turn people into monsters.&#xA;Viewing life as a movie, Erind&#x2019;s wish to become the main character is granted unexpectedly: (...)">
    <meta property="books:rating:value" content="4.898785"/>
    <meta property="books:rating:scale" content="5"/>
    <meta property="books:author" content="Temple"/>
    <meta property="books:isbn" content=""/>
    <meta name="twitter:card" content="summary">
    <meta name="twitter:site" content="@RoyalRoadL">
    <meta name="twitter:creator" content="Temple">
    <meta name="twitter:title" content="REND">
    <meta name="twitter:description" content="Erind Hartwell: dutiful daughter, law student, psychopath, film enthusiast&#x2014;one of these makes her not normal. Was it the psychopath thing? Maybe. Still, she&#x27;s relatively normal in a world where superhumans (...)">
    <meta name="twitter:image" content="https://www.royalroadcdn.com/public/covers-large/117255-rend.jpg?time=1748727569">
    <link rel="canonical" href="https://www.royalroad.com/fiction/117255/rend"/>
    <link rel="alternate" type="application/rss+xml" title="Updates for REND" href="/syndication/117255"/>

    <link href="https://fonts.googleapis.com/css2?family=Open+Sans:ital,wght@0,300;0,400;0,600;0,700;1,400&display=swap" rel="stylesheet">
    <link type="text/css" rel="stylesheet" href="/dist/vendor.css?v=Twkv0-0SZkUAMvQBlPbXWCBEntpE1nxTV27fJ3DR4M4" />
    <link type="text/css" rel="stylesheet" href="/dist/site-light.css?v=UUh22Cvu8gmehId2hg0CW3WSKym_KlnGjVLx-cJsq_s" />

    <style>
        #cover-lightbox.modal {
          text-align: center;
        }

        @media screen and (min-width: 768px) {
          #cover-lightbox.modal:before {
            display: inline-block;
            vertical-align: middle;
            content: " ";
            height: 100%;
          }
        }

        #cover-lightbox .modal-dialog {
          display: inline-block;
          text-align: left;
          vertical-align: middle;
        }
    </style>
    <script type="application/ld+json">{"@context":"https://schema.org","@type":"Book","name":"REND","description":"<p>Erind Hartwell: dutiful daughter, law student, psychopath, film enthusiast—one of these makes her not normal. Was it the psychopath thing? Maybe. Still, she's relatively normal in a world where superhumans fight eldritch horrors that turn people into monsters.</p>\n<p>Viewing life as a movie, Erind’s wish to become the main character is granted unexpectedly: on the brink of death, an otherworldly entity offers her powers. Becoming a monster doesn’t sound like how a main character should be, but there isn’t much of a choice, as she was dying, impaled by a spike. She can probably make this monster thing work.</p>\n<p>Follow an endearing psychopath and her shenanigans in the middle of a battle between superhumans, hi-tech government agents, monsters, mutants, and wannabe heroes for Earth and the future of humanity.</p>\n<hr>\n<p>This is a rewrite of <a href=\"https://www.royalroad.com/fiction/32615/rend\" rel=\"noopener ugc nofollow\">REND: Prior Cycle (Old Version)</a>. 90+% different from the original. <br>Cover art by ChristianAC</p>","image":"https://www.royalroadcdn.com/public/covers-large/117255-rend.jpg?time=1748727569","mainEntityOfPage":"https://www.royalroad.com/fiction/117255/rend","potentialAction":{"@type":"ReadAction","name":"REND","target":{"@type":"EntryPoint","actionPlatform":["http://schema.org/DesktopWebPlatform","http://schema.org/MobileWebPlatform","http://schema.org/AndroidPlatform","http://schema.org/iOSPlatform"],"urlTemplate":"https://www.royalroad.com/fiction/117255/rend"}},"url":"https://www.royalroad.com/fiction/117255/rend","aggregateRating":{"@type":"AggregateRating","bestRating":5,"ratingValue":4.89878511428833,"worstRating":0.5,"ratingCount":247},"author":{"@type":"Person","name":"Temple"},"genre":["Action","Comedy","Fantasy","Psychological","Anti-Hero Lead","Female Lead","Low Fantasy","Progression","Secret Identity","Strong Lead","Super Heroes","Supernatural","Urban Fantasy","Villainous Lead"],"headline":"REND","publisher":{"@type":"Organization","name":"Royal Road","url":"https://www.royalroad.com/","logo":"https://www.royalroad.com/dist/img/logo/rr-logo-square-silver-gold-large.png"},"numberOfPages":115}</script>

    <link rel="icon" href="/icons/android-chrome-192x192.png?v=20200125" sizes="192x192" />
    <link rel="shortcut icon" href="/icons/favicon.ico?v=20200125" sizes="16x16 24x24 32x32"/>
    <link rel="apple-touch-icon" sizes="180x180" href="/icons/apple-icon-180x180.png?v=20200125">
    <link rel="icon" type="image/png" sizes="16x16" href="/icons/favicon-16x16.png?v=20200125">
    <link rel="icon" type="image/png" sizes="32x32" href="/icons/favicon-32x32.png?v=20200125">
    <link rel="manifest" href="/manifest.json">
    <meta name="msapplication-TileColor" content="#ffffff">
    <meta name="msapplication-TileImage" content="/icons/ms-icon-144x144.png">
    <meta name="theme-color" content="#FFFFFF">
        <meta name="sentry-trace" content="25608656142b476ca0f8682a181d16e9-8c41d707a9fc6385"/>
        <meta name="baggage" content="sentry-trace_id=25608656142b476ca0f8682a181d16e9, sentry-public_key=de5ce8f509e7458780cbb83f5b040bf0, sentry-release=RoyalRoad.Web.Website%404.1.20250603.1, sentry-environment=production">
    <script type="text/javascript">
        window.royalroad = window.royalroad || {init: []};
        window.royalroad.isPremium = false;
        window.royalroad.version = "RoyalRoad.Web.Website@"+"4.1.20250603.1";
        window.royalroad.userId = 0;
        window.royalroad.environment = "Production";
        window.royalroad.actionRoute = "Fictions.Index";
        window.royalroad.username = "";
        window.royalroad.betaFeatures = false;

        window.dateFormat = "yyyy-MM-dd";
        window.dateTimeFormat = "yyyy-MM-dd HH:mm";
    </script>
    <script type="text/javascript" src="https://cdnjs.cloudflare.com/polyfill/v3/polyfill.min.js?features=default%2Ces6"></script>
<script>('WeakMap' in window && 'IntersectionObserver' in window && 'assign' in Object && 'fetch' in window||document.write("\u003Cscript type=\u0022text/javascript\u0022 src=\u0022/dist/polyfill.js\u0022\u003E\u003C/script\u003E"));</script>

<script type="text/javascript">var AdblockPlus=new function(){this.detect=function(n,e){var o=!1,r=2,c=!1,t=!1;if("function"==typeof e){n+="?ch=*&rn=*";var a=11*Math.random(),i=new Image;i.onload=u,i.onerror=function(){c=!0,u()},i.src=n.replace(/\*/,1).replace(/\*/,a);var f=new Image;f.onload=u,f.onerror=function(){t=!0,u()},f.src=n.replace(/\*/,2).replace(/\*/,a),function n(e,c){0==r||c>1e3?e(0==r&&o):setTimeout(function(){n(e,2*c)},2*c)}(e,250)}function u(){--r||(o=!c&&t)}}};</script><script type="text/javascript">window.nitroAds=window.nitroAds||{createAd:function(){return new Promise(e=>{window.nitroAds.queue.push(["createAd",arguments,e])})},addUserToken:function(){window.nitroAds.queue.push(["addUserToken",arguments])},queue:[]};</script><script async="async" src="https://s.nitropay.com/ads-137.js" type="text/javascript"></script></head>
<body class="page-container-bg-solid light-theme">
<div class="page-container">
    <div class="page-content-wrapper">
        <div class="page-content">
            <div class="container fiction-page">
<div class="row fic-header">
    <div class="col-md-3 text-center cover-col">
        <div class="cover-art-container">
            <img class="thumbnail inline-block" data-type="cover" onLoad="this.dataset.loaded = 1" onError="this.onerror=null; this.src=&#x27;/dist/img/nocover-new-min.png&#x27;" alt="REND" src="https://www.royalroadcdn.com/public/covers-large/117255-rend.jpg?time=1748727569"></img>
        </div>
    </div>
    <div class="col-md-5 col-lg-6 text-center md-text-left fic-title">
        <div class="col">
            <h1 class="font-white">REND</h1>
            <h4 class="font-white">
                <span class="small font-white">by </span>
                <span>
                    <a href="/profile/165560" class="font-white">Temple</a>
                </span>
            </h4>
        </div>
    </div>
</div>
<div class="fiction row">
<div class="col-sm-12">
<div class="fiction-info">
<div class="portlet light row" style="min-height: 180px;">
    <div class="col-md-4"></div>
    <div class="col-md-8">
        <div class="description">
            <input type="checkbox" value="" id="showMore"/>
            <div class="hidden-content">
                <p>Erind Hartwell: dutiful daughter, law student, psychopath, film enthusiast—one of these makes her not normal. Was it the psychopath thing? Maybe. Still, she's relatively normal in a world where superhumans fight eldritch horrors that turn people into monsters.</p>
<p>Viewing life as a movie, Erind’s wish to become the main character is granted unexpectedly: on the brink of death, an otherworldly entity offers her powers. Becoming a monster doesn’t sound like how a main character should be, but there isn’t much of a choice, as she was dying, impaled by a spike. She can probably make this monster thing work.</p>
<p>Follow an endearing psychopath and her shenanigans in the middle of a battle between superhumans, hi-tech government agents, monsters, mutants, and wannabe heroes for Earth and the future of humanity.</p>
<hr>
<p>This is a rewrite of <a href="https://www.royalroad.com/fiction/32615/rend" rel="noopener ugc nofollow">REND: Prior Cycle (Old Version)</a>. 90+% different from the original. <br>Cover art by ChristianAC</p>
            </div>
            <label for="showMore" class="bold uppercase small"></label>
        </div>
    </div>
</div>
<div class="portlet light">
    <div class="portlet-body">
        <table class="table no-border" id="chapters" data-chapters="12">
            <thead>
            <tr>
                <th data-priority="1">
                    Chapter Name
                </th>
                <th class="text-right min-tablet-p" data-priority="2">
                    Release Date
                </th>
            </tr>
            </thead>
            <tbody>
                <tr style="cursor: pointer" data-url="/fiction/117255/rend/chapter/2291798/11-crappy-monday" data-volume-id="null" class="chapter-row">
                    <td>
                        <a href="/fiction/117255/rend/chapter/2291798/11-crappy-monday">
                            1.1 Crappy Monday
                        </a>
                    </td>
                    <td data-content="0" class="text-right">
                        <a href="/fiction/117255/rend/chapter/2291798/11-crappy-monday" data-content="0">
                            <time unixtime="1747702533" title="Tuesday, May 20, 2025 12:55:33&#x202F;AM" datetime="2025-05-20T00:55:33.0000000&#x2B;00:00" format="agoshort">14 days </time> ago
                        </a>
                    </td>
                </tr>
                <tr style="cursor: pointer" data-url="/fiction/117255/rend/chapter/2292710/12-crappy-monday" data-volume-id="null" class="chapter-row">
                    <td>
                        <a href="/fiction/117255/rend/chapter/2292710/12-crappy-monday">
                            1.2 Crappy Monday
                        </a>
                    </td>
                    <td data-content="1" class="text-right">
                        <a href="/fiction/117255/rend/chapter/2292710/12-crappy-monday" data-content="1">
                            <time unixtime="1747744209" title="Tuesday, May 20, 2025 12:30:09&#x202F;PM" datetime="2025-05-20T12:30:09.0000000&#x2B;00:00" format="agoshort">14 days </time> ago
                        </a>
                    </td>
                </tr>
                <tr style="cursor: pointer" data-url="/fiction/117255/rend/chapter/2295018/13-crappy-monday" data-volume-id="null" class="chapter-row">
                    <td>
                        <a href="/fiction/117255/rend/chapter/2295018/13-crappy-monday">
                            1.3 Crappy Monday
                        </a>
                    </td>
                    <td data-content="2" class="text-right">
                        <a href="/fiction/117255/rend/chapter/2295018/13-crappy-monday" data-content="2">
                            <time unixtime="1747832621" title="Wednesday, May 21, 2025 1:03:41&#x202F;PM" datetime="2025-05-21T13:03:41.0000000&#x2B;00:00" format="agoshort">13 days </time> ago
                        </a>
                    </td>
                </tr>
                <tr style="cursor: pointer" data-url="/fiction/117255/rend/chapter/2296785/14-crappy-monday" data-volume-id="null" class="chapter-row">
                    <td>
                        <a href="/fiction/117255/rend/chapter/2296785/14-crappy-monday">
                            1.4 Crappy Monday
                        </a>
                    </td>
                    <td data-content="3" class="text-right">
                        <a href="/fiction/117255/rend/chapter/2296785/14-crappy-monday" data-content="3">
                            <time unixtime="1747889398" title="Thursday, May 22, 2025 4:49:58&#x202F;AM" datetime="2025-05-22T04:49:58.0000000&#x2B;00:00" format="agoshort">12 days </time> ago
                        </a>
                    </td>
                </tr>
                <tr style="cursor: pointer" data-url="/fiction/117255/rend/chapter/2299364/21-new-semester-new-me" data-volume-id="null" class="chapter-row">
                    <td>
                        <a href="/fiction/117255/rend/chapter/2299364/21-new-semester-new-me">
                            2.1 New Semester, New Me
                        </a>
                    </td>
                    <td data-content="4" class="text-right">
                        <a href="/fiction/117255/rend/chapter/2299364/21-new-semester-new-me" data-content="4">
                            <time unixtime="1747986363" title="Friday, May 23, 2025 7:46:03&#x202F;AM" datetime="2025-05-23T07:46:03.0000000&#x2B;00:00" format="agoshort">11 days </time> ago
                        </a>
                    </td>
                </tr>
                <tr style="cursor: pointer" data-url="/fiction/117255/rend/chapter/2301568/22-new-semester-new-me" data-volume-id="null" class="chapter-row">
                    <td>
                        <a href="/fiction/117255/rend/chapter/2301568/22-new-semester-new-me">
                            2.2 New Semester, New Me
                        </a>
                    </td>
                    <td data-content="5" class="text-right">
                        <a href="/fiction/117255/rend/chapter/2301568/22-new-semester-new-me" data-content="5">
                            <time unixtime="1748048108" title="Saturday, May 24, 2025 12:55:08&#x202F;AM" datetime="2025-05-24T00:55:08.0000000&#x2B;00:00" format="agoshort">10 days </time> ago
                        </a>
                    </td>
                </tr>
                <tr style="cursor: pointer" data-url="/fiction/117255/rend/chapter/2303699/23-new-semester-new-me" data-volume-id="null" class="chapter-row">
                    <td>
                        <a href="/fiction/117255/rend/chapter/2303699/23-new-semester-new-me">
                            2.3 New Semester, New Me
                        </a>
                    </td>
                    <td data-content="6" class="text-right">
                        <a href="/fiction/117255/rend/chapter/2303699/23-new-semester-new-me" data-content="6">
                            <time unixtime="1748137542" title="Sunday, May 25, 2025 1:45:42&#x202F;AM" datetime="2025-05-25T01:45:42.0000000&#x2B;00:00" format="agoshort">9 days </time> ago
                        </a>
                    </td>
                </tr>
                <tr style="cursor: pointer" data-url="/fiction/117255/rend/chapter/2305732/24-new-semester-new-me" data-volume-id="null" class="chapter-row">
                    <td>
                        <a href="/fiction/117255/rend/chapter/2305732/24-new-semester-new-me">
                            2.4 New Semester, New Me
                        </a>
                    </td>
                    <td data-content="7" class="text-right">
                        <a href="/fiction/117255/rend/chapter/2305732/24-new-semester-new-me" data-content="7">
                            <time unixtime="1748226404" title="Monday, May 26, 2025 2:26:44&#x202F;AM" datetime="2025-05-26T02:26:44.0000000&#x2B;00:00" format="agoshort">8 days </time> ago
                        </a>
                    </td>
                </tr>
                <tr style="cursor: pointer" data-url="/fiction/117255/rend/chapter/2311648/31-those-above-the-law" data-volume-id="null" class="chapter-row">
                    <td>
                        <a href="/fiction/117255/rend/chapter/2311648/31-those-above-the-law">
                            3.1 Those Above the Law
                        </a>
                    </td>
                    <td data-content="8" class="text-right">
                        <a href="/fiction/117255/rend/chapter/2311648/31-those-above-the-law" data-content="8">
                            <time unixtime="1748440338" title="Wednesday, May 28, 2025 1:52:18&#x202F;PM" datetime="2025-05-28T13:52:18.0000000&#x2B;00:00" format="agoshort">6 days </time> ago
                        </a>
                    </td>
                </tr>
                <tr style="cursor: pointer" data-url="/fiction/117255/rend/chapter/2316851/32-those-above-the-law" data-volume-id="null" class="chapter-row">
                    <td>
                        <a href="/fiction/117255/rend/chapter/2316851/32-those-above-the-law">
                            3.2 Those Above the Law
                        </a>
                    </td>
                    <td data-content="9" class="text-right">
                        <a href="/fiction/117255/rend/chapter/2316851/32-those-above-the-law" data-content="9">
                            <time unixtime="1748612175" title="Friday, May 30, 2025 1:36:15&#x202F;PM" datetime="2025-05-30T13:36:15.0000000&#x2B;00:00" format="agoshort">4 days </time> ago
                        </a>
                    </td>
                </tr>
                <tr style="cursor: pointer" data-url="/fiction/117255/rend/chapter/2319836/33-those-above-the-law" data-volume-id="null" class="chapter-row">
                    <td>
                        <a href="/fiction/117255/rend/chapter/2319836/33-those-above-the-law">
                            3.3 Those Above the Law
                        </a>
                    </td>
                    <td data-content="10" class="text-right">
                        <a href="/fiction/117255/rend/chapter/2319836/33-those-above-the-law" data-content="10">
                            <time unixtime="1748707292" title="Saturday, May 31, 2025 4:01:32&#x202F;PM" datetime="2025-05-31T16:01:32.0000000&#x2B;00:00" format="agoshort">3 days </time> ago
                        </a>
                    </td>
                </tr>
                <tr style="cursor: pointer" data-url="/fiction/117255/rend/chapter/2322033/41-a-memorial-to-remember" data-volume-id="null" class="chapter-row">
                    <td>
                        <a href="/fiction/117255/rend/chapter/2322033/41-a-memorial-to-remember">
                            4.1 A Memorial To Remember
                        </a>
                    </td>
                    <td data-content="11" class="text-right">
                        <a href="/fiction/117255/rend/chapter/2322033/41-a-memorial-to-remember" data-content="11">
                            <time unixtime="1748789627" title="Sunday, June 1, 2025 2:53:47&#x202F;PM" datetime="2025-06-01T14:53:47.0000000&#x2B;00:00" format="agoshort">2 days </time> ago
                        </a>
                    </td>
                </tr>
            </tbody>
        </table>
    </div>
</div>
</div>
</div>
</div>
            </div>
        </div>
    </div>
</div>
</body>
</html>
""" # Truncated for brevity, full HTML is very long

class RoyalRoadFetcher(BaseFetcher):
    def _fetch_html_content(self, url: str) -> BeautifulSoup:
        # In a real application, this would use 'requests' to get the HTML
        # For now, it uses the example HTML if the URL matches, otherwise raises an error
        # This is a simplified approach for the current phase.
        # The provided URL in the issue is https://www.royalroad.com/fiction/117255/rend
        if "royalroad.com/fiction/117255/rend" in url:
            return BeautifulSoup(EXAMPLE_STORY_PAGE_HTML, 'html.parser')
        elif "chapter" in url: # Simulate fetching chapter content
             # For now, we don't have example chapter HTML, so we'll return a mock soup
             # or the main page soup. This part will need actual chapter HTML for parsing.
            return BeautifulSoup(f"<html><body><h1>Chapter Content for {url}</h1><div class='chapter-content'>This is placeholder chapter content.</div></body></html>", 'html.parser')
        else:
            # This will be replaced by actual HTTP requests and error handling
            raise NotImplementedError(f"Fetching for URL '{url}' is not implemented with example HTML. "
                                      "Actual HTTP requests are needed for dynamic content.")

    def get_story_metadata(self, url: str) -> StoryMetadata:
        # For now, we will use the example HTML content for parsing.
        # In a real scenario, the content would be fetched using self._fetch_html_content(url)
        # or a dedicated request if EXAMPLE_STORY_PAGE_HTML is not suitable.

        # soup = self._fetch_html_content(url) # This would be the ideal call

        # Using the global example HTML for now, as per plan
        soup = BeautifulSoup(EXAMPLE_STORY_PAGE_HTML, 'html.parser')

        metadata = StoryMetadata()
        metadata.story_url = url

        # Title
        title_tag = soup.find('h1', class_='font-white')
        if title_tag:
            metadata.original_title = title_tag.text.strip()
        else: # Fallback to meta property
            og_title_tag = soup.find('meta', property='og:title')
            if og_title_tag and og_title_tag.get('content'):
                 metadata.original_title = og_title_tag['content']
            else: # Fallback to document title if specific tags are missing
                doc_title_tag = soup.find('title')
                if doc_title_tag:
                    title_text = doc_title_tag.text.strip()
                    # Remove " | Royal Road" suffix
                    metadata.original_title = title_text.replace(" | Royal Road", "").strip()


        # Author
        author_link = soup.select_one('h4.font-white a[href*="/profile/"]')
        if author_link:
            metadata.original_author = author_link.text.strip()
        else: # Fallback to meta property
            meta_author_tag = soup.find('meta', property='books:author')
            if meta_author_tag and meta_author_tag.get('content'):
                metadata.original_author = meta_author_tag['content']


        # Cover Image URL
        cover_img_tag = soup.select_one('div.cover-art-container img.thumbnail')
        if cover_img_tag and cover_img_tag.get('src'):
            metadata.cover_image_url = cover_img_tag['src']
        else: # Fallback to meta property
            og_image_tag = soup.find('meta', property='og:image')
            if og_image_tag and og_image_tag.get('content'):
                metadata.cover_image_url = og_image_tag['content']

        # Synopsis
        # Try the schema.org description first as it's often cleaner
        schema_script = soup.find('script', type='application/ld+json')
        if schema_script:
            import json
            try:
                schema_data = json.loads(schema_script.string)
                if schema_data.get('@type') == 'Book' and schema_data.get('description'):
                    # Basic cleaning for synopsis from schema: remove <p>, <br>, <hr>
                    synopsis_html = schema_data['description']
                    synopsis_soup = BeautifulSoup(synopsis_html, 'html.parser')
                    # Replace <br> and <hr> with newlines, then get text
                    for br in synopsis_soup.find_all("br"):
                        br.replace_with("\n")
                    for hr in synopsis_soup.find_all("hr"):
                        hr.replace_with("\n---\n")
                    metadata.synopsis = synopsis_soup.get_text(separator='\n').strip()

            except json.JSONDecodeError:
                pass # Fallback if JSON is malformed

        if not metadata.synopsis: # Fallback to the description div if schema fails or not present
            description_div = soup.select_one('div.description div.hidden-content')
            if description_div:
                # Convert <p> tags to text with newlines, <hr> to separator
                ps = []
                for element in description_div.children:
                    if isinstance(element, Tag):
                        if element.name == 'p':
                            ps.append(element.get_text(strip=True))
                        elif element.name == 'hr':
                            ps.append("---")
                metadata.synopsis = "\n\n".join(ps).strip()

        # Estimated total chapters from source (from the table#chapters data-chapters attribute)
        chapters_table = soup.find('table', id='chapters')
        if chapters_table and chapters_table.has_attr('data-chapters'):
            try:
                metadata.estimated_total_chapters_source = int(chapters_table['data-chapters'])
            except ValueError:
                metadata.estimated_total_chapters_source = None # Or some other default/logging

        return metadata

    def get_chapter_urls(self, story_url: str) -> List[ChapterInfo]:
        # For now, we will use the example HTML content for parsing.
        # soup = self._fetch_html_content(story_url) # Ideal call
        soup = BeautifulSoup(EXAMPLE_STORY_PAGE_HTML, 'html.parser') # Using global example for now

        chapters: List[ChapterInfo] = []
        chapter_table = soup.find('table', id='chapters')
        if not chapter_table:
            return chapters

        base_url = "https://www.royalroad.com" # Needed to construct full URLs

        for order, row in enumerate(chapter_table.find('tbody').find_all('tr', class_='chapter-row')):
            link_tag = row.find('a')
            if link_tag and link_tag.has_attr('href'):
                chapter_relative_url = link_tag['href']
                full_chapter_url = base_url + chapter_relative_url if chapter_relative_url.startswith('/') else chapter_relative_url

                chapter_title_text = link_tag.text.strip()

                # Try to extract a source_chapter_id from the URL, e.g., the numeric part
                # Example: /fiction/117255/rend/chapter/2291798/11-crappy-monday -> 2291798
                match = re.search(r'/chapter/(\d+)/', full_chapter_url)
                source_id = match.group(1) if match else f"order_{order + 1}"

                chapters.append(ChapterInfo(
                    source_chapter_id=source_id,
                    download_order=order + 1,
                    chapter_url=full_chapter_url,
                    chapter_title=chapter_title_text
                ))
        return chapters

    def download_chapter_content(self, chapter_url: str) -> str:
        # This is a placeholder for Phase 1.
        # In a real scenario, this would fetch the HTML content of the chapter_url.
        # soup = self._fetch_html_content(chapter_url)
        # chapter_div = soup.find('div', class_='chapter-content') # Or similar selector
        # return str(chapter_div) if chapter_div else "Chapter content not found."

        print(f"Simulating download of chapter: {chapter_url}") # For now, just print
        return f"<html><body><h1>Placeholder Content for {chapter_url}</h1><div class='chapter-content'><p>This is simulated raw HTML content for the chapter.</p><script>alert('test');</script><style>.useless{color:red;}</style></div></body></html>"

if __name__ == '__main__':
    # Example usage for testing (will be part of actual test files later)
    fetcher = RoyalRoadFetcher()
    story_url_example = "https://www.royalroad.com/fiction/117255/rend" # Matches example HTML

    print("--- Story Metadata ---")
    metadata = fetcher.get_story_metadata(story_url_example)
    print(f"Title: {metadata.original_title}")
    print(f"Author: {metadata.original_author}")
    print(f"Cover URL: {metadata.cover_image_url}")
    print(f"Synopsis: {metadata.synopsis[:200]}...") # Print first 200 chars
    print(f"Est. Chapters: {metadata.estimated_total_chapters_source}")
    print(f"Story URL: {metadata.story_url}")


    print("\n--- Chapter List ---")
    chapters = fetcher.get_chapter_urls(story_url_example)
    if chapters:
        for i, chap in enumerate(chapters[:5]): # Print first 5 chapters
            print(f"Order: {chap.download_order}, Source ID: {chap.source_chapter_id}, Title: {chap.chapter_title}, URL: {chap.chapter_url}")
        if len(chapters) > 5:
            print(f"... and {len(chapters) - 5} more chapters.")
    else:
        print("No chapters found.")

    print("\n--- Download Chapter Content (Simulation) ---")
    if chapters:
        # Simulate downloading the first chapter's content
        first_chapter_content = fetcher.download_chapter_content(chapters[0].chapter_url)
        print(f"Content for '{chapters[0].chapter_title}':\n{first_chapter_content[:300]}...") # Print first 300 chars
    else:
        print("No chapters to simulate download for.")
