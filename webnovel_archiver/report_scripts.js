// Global variables
let currentPage = 1;
const itemsPerPage = 25; // Number of items per page
let allVisibleStoryCards = []; // To store all cards initially or after filtering/sorting

// DOM Element caching (populated in DOMContentLoaded)
let searchInput = null;
let filterStatusSelect = null;
let sortSelect = null;
let storyListContainer = null;
let paginationControls = null;

// Modal elements
let modal = null;
let modalCloseBtn = null;
let modalBodyContent = null;

function toggleSynopsis(element) {
    element.classList.toggle('expanded');
    const toggleLink = element.nextElementSibling;
    if (element.classList.contains('expanded')) {
        toggleLink.textContent = '(Read less)';
    } else {
        toggleLink.textContent = '(Read more)';
    }
}

function displayPage(pageNumber, currentItems) {
    currentPage = pageNumber;
    const startIndex = (pageNumber - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;

    // Hide all cards in the current set first
    currentItems.forEach(card => card.style.display = 'none');

    // Show only the cards for the current page
    const pageItems = currentItems.slice(startIndex, endIndex);
    pageItems.forEach(card => card.style.display = 'flex'); // Assuming 'flex' is the default display

    updatePaginationControlsUI(currentItems.length);
}

function updatePaginationControlsUI(totalItemsCount) {
    if (!paginationControls) return; // Ensure paginationControls is cached

    const totalPages = Math.ceil(totalItemsCount / itemsPerPage);

    const pageLinks = paginationControls.querySelectorAll('.page-link');
    pageLinks.forEach(link => {
        link.classList.remove('active');
        if (parseInt(link.dataset.page) === currentPage) {
            link.classList.add('active');
        }
    });

    const prevButton = paginationControls.querySelector('.page-button[data-action="prev"]');
    const nextButton = paginationControls.querySelector('.page-button[data-action="next"]');

    if (prevButton) {
        prevButton.classList.toggle('disabled', currentPage === 1);
    }
    if (nextButton) {
        nextButton.classList.toggle('disabled', currentPage === totalPages || totalPages === 0);
    }
}

function setupPaginationControls(totalItemsCount, itemsPerPage, containerId, displayFnForPageChange) {
    const container = document.getElementById(containerId); // paginationControls is already cached
    if (!container) return;
    container.innerHTML = ''; // Clear existing controls

    const totalPages = Math.ceil(totalItemsCount / itemsPerPage);
    if (totalPages <= 1) return; // No controls needed for single page

    let paginationHTML = '';

    // Previous Button
    paginationHTML += `<button class="page-button" data-action="prev">&laquo; Prev</button>`;

    // Page Number Links
    for (let i = 1; i <= totalPages; i++) {
        if (i === 1 || i === totalPages || (i >= currentPage - 2 && i <= currentPage + 2)) {
             paginationHTML += `<a href="#" class="page-link" data-page="${i}">${i}</a>`;
        } else if (i === currentPage - 3 || i === currentPage + 3) {
             paginationHTML += `<span class="page-ellipsis">...</span>`;
        }
    }

    // Next Button
    paginationHTML += `<button class="page-button" data-action="next">&raquo; Next</button>`;

    container.innerHTML = paginationHTML;

    // Add event listeners
    container.querySelectorAll('.page-button, .page-link').forEach(el => {
        el.addEventListener('click', function(event) {
            event.preventDefault();
            const pageAction = this.dataset.action;
            const pageNum = this.dataset.page;
            let newPageToDisplay;

            if (pageAction === 'prev') {
                newPageToDisplay = currentPage - 1;
            } else if (pageAction === 'next') {
                newPageToDisplay = currentPage + 1;
            } else if (pageNum) {
                newPageToDisplay = parseInt(pageNum);
            }

            if (newPageToDisplay) {
                 handlePageChange(newPageToDisplay, totalItemsCount, displayFnForPageChange);
            }
        });
    });
}

function handlePageChange(newPage, totalItems, displayFn) {
    const totalPages = Math.ceil(totalItems / itemsPerPage);
    if (newPage < 1 || newPage > totalPages) return;
    displayFn(newPage, allVisibleStoryCards); // displayFn is displayPage
}

function filterStories() {
    if (!searchInput || !filterStatusSelect || !storyListContainer) return; // Ensure elements are cached

    let filterTitle = searchInput.value.toUpperCase();
    let statusFilter = filterStatusSelect.value;

    // Reset to all cards from the DOM before filtering
    // This assumes all cards are initially within storyListContainer
    const originalCards = Array.from(storyListContainer.children).filter(child => child.classList.contains('story-card'));

    allVisibleStoryCards = originalCards.filter(card => {
        let title = (card.dataset.title || '').toUpperCase();
        let author = (card.dataset.author || '').toUpperCase();
        let status = card.dataset.status || '';

        let titleMatch = title.includes(filterTitle) || author.includes(filterTitle);
        let statusMatch = (statusFilter === "" || status === statusFilter);
        return titleMatch && statusMatch;
    });

    // No direct DOM manipulation for filtering here; pagination handles display
    setupPaginationControls(allVisibleStoryCards.length, itemsPerPage, 'paginationControls', displayPage);
    displayPage(1, allVisibleStoryCards);
}

function sortStories() {
    if (!sortSelect || !storyListContainer) return; // Ensure elements are cached

    let sortValue = sortSelect.value;

    // If allVisibleStoryCards is empty (e.g. after a filter that returns no results),
    // or if it hasn't been populated yet (e.g. sort is the first action before any filtering/initial load processing)
    // we should ensure it's populated.
    if (!allVisibleStoryCards || allVisibleStoryCards.length === 0) {
        const currentCardsInDOM = Array.from(storyListContainer.children).filter(child => child.classList.contains('story-card'));
         // Check if cards are currently displayed by a filter or if it's an empty filter result
        const activeFilter = searchInput.value || filterStatusSelect.value;
        if (!activeFilter && currentCardsInDOM.length > 0) {
            // If no filter is active, and cards are in DOM, use them (e.g. initial load, no filter applied yet)
            allVisibleStoryCards = currentCardsInDOM;
        } else if (!activeFilter && currentCardsInDOM.length === 0 && allVisibleStoryCards.length === 0) {
            // True initial load, no cards in allVisibleStoryCards, no cards in DOM (they are all display:none by default until first displayPage)
            // So, get all cards from the container.
            allVisibleStoryCards = Array.from(document.querySelectorAll('#storyListContainer .story-card'));
        }
        // If a filter is active and resulted in zero cards, allVisibleStoryCards is already correctly empty.
    }


    allVisibleStoryCards.sort(function(a, b) {
        let valA, valB;
        switch (sortValue) {
            case 'title':
                valA = a.dataset.title || '';
                valB = b.dataset.title || '';
                return valA.localeCompare(valB);
            case 'last_updated_desc':
                valA = a.dataset.lastUpdated || '';
                valB = b.dataset.lastUpdated || '';
                return valB.localeCompare(valA); // Descending
            case 'last_updated_asc':
                valA = a.dataset.lastUpdated || '';
                valB = b.dataset.lastUpdated || '';
                return valA.localeCompare(valB); // Ascending
            case 'progress_desc':
                valA = parseInt(a.dataset.progress || 0);
                valB = parseInt(b.dataset.progress || 0);
                return valB - valA; // Descending
            default:
                return 0;
        }
    });

    // displayPage will handle showing the sorted cards from allVisibleStoryCards.
    // No direct DOM manipulation for sorting here.
    setupPaginationControls(allVisibleStoryCards.length, itemsPerPage, 'paginationControls', displayPage);
    displayPage(1, allVisibleStoryCards);
}

function toggleExtraEpubs(story_id_sanitized, buttonElement, totalEpubs, threshold) {
    const moreEpubsDiv = document.getElementById(`more-epubs-${story_id_sanitized}`);
    if (moreEpubsDiv) {
        const isHidden = moreEpubsDiv.style.display === 'none';
        moreEpubsDiv.style.display = isHidden ? 'block' : 'none';
        if (isHidden) {
            buttonElement.textContent = 'Show fewer EPUBs';
        } else {
            buttonElement.textContent = `Show all ${totalEpubs} EPUBs`;
        }
    }
}

document.addEventListener('DOMContentLoaded', function() {
    // Cache DOM elements
    searchInput = document.getElementById('searchInput');
    filterStatusSelect = document.getElementById('filterStatusSelect');
    sortSelect = document.getElementById('sortSelect');
    storyListContainer = document.getElementById('storyListContainer');
    paginationControls = document.getElementById('paginationControls');

    if (storyListContainer) {
        // Get all cards present in the container at load time
        allVisibleStoryCards = Array.from(storyListContainer.children).filter(child => child.classList.contains('story-card'));

        if (allVisibleStoryCards.length > 0) {
            setupPaginationControls(allVisibleStoryCards.length, itemsPerPage, 'paginationControls', displayPage);
            displayPage(1, allVisibleStoryCards);
        } else {
            // Handle case where storyListContainer is empty or has no story-cards
            // console.log("No story cards found on initial load.");
            // Still setup pagination controls (it will show nothing if totalItems is 0)
             setupPaginationControls(0, itemsPerPage, 'paginationControls', displayPage);
             displayPage(1, []); // Display an empty page
        }
    } else {
        // console.error("Story list container not found.");
    }

    // Add event listeners for filter and sort controls
    if (searchInput) {
        searchInput.addEventListener('keyup', filterStories);
    }
    if (filterStatusSelect) {
        filterStatusSelect.addEventListener('change', filterStories);
    }
    if (sortSelect) {
        sortSelect.addEventListener('change', sortStories);
    }

    // Modal elements caching
    modal = document.getElementById('storyDetailModal');
    modalCloseBtn = document.querySelector('.modal-close-btn'); // Assuming only one such button
    modalBodyContent = document.getElementById('modalBodyContent');

    // Event listener for "View Details" buttons (using event delegation)
    if (storyListContainer) {
        storyListContainer.addEventListener('click', function(event) {
            const button = event.target.closest('.view-details-btn');
            if (button) {
                openModalWithStoryData(button);
            }
        });
    }

    // Event listener for modal close button
    if (modalCloseBtn) {
        modalCloseBtn.onclick = function() {
            if (modal) {
                modal.style.display = 'none';
            }
            if (modalBodyContent) {
                modalBodyContent.innerHTML = ''; // Clear content for next time
            }
        };
    }

    // Event listener for clicking outside the modal content to close
    if (modal) {
        window.onclick = function(event) {
            if (event.target == modal) {
                modal.style.display = 'none';
                if (modalBodyContent) {
                    modalBodyContent.innerHTML = ''; // Clear content
                }
            }
        };
    }
});

// Function to open modal and populate it with story data
function openModalWithStoryData(buttonElement) {
    if (!modal || !modalBodyContent) {
        console.error('Modal elements not found.');
        return;
    }

    const storyCard = buttonElement.closest('.story-card');
    if (!storyCard) {
        console.error('Parent story card not found for the button.');
        return;
    }

    const modalContentSource = storyCard.querySelector('.story-card-modal-content');
    if (!modalContentSource) {
        console.error('Modal content source div not found in the story card.');
        return;
    }

    modalBodyContent.innerHTML = modalContentSource.innerHTML;
    modal.style.display = 'block';
}
