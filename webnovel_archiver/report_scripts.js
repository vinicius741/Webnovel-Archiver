// Global variables
let currentPage = 1;
const itemsPerPage = 25; // Number of items per page
let masterStoryCards = []; // Holds all story cards, never changes after load
let allVisibleStoryCards = []; // Holds currently visible/filtered/sorted cards

// DOM Element caching (populated in DOMContentLoaded)
let searchInput = null;
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

function updateDisplayedCards() {
    if (!searchInput || !sortSelect || !storyListContainer) {
        // console.warn("updateDisplayedCards called before DOM elements are cached.");
        return;
    }

    const filterText = searchInput.value.toUpperCase();
    const sortValue = sortSelect.value;

    // 1. Filter masterStoryCards
    let filteredCards;
    if (filterText) {
        filteredCards = masterStoryCards.filter(card => {
            let title = (card.dataset.title || '').toUpperCase();
            let author = (card.dataset.author || '').toUpperCase();
            return title.includes(filterText) || author.includes(filterText);
        });
    } else {
        filteredCards = [...masterStoryCards]; // If no filter, use all master cards
    }

    // 2. Sort a copy of filteredCards
    // Create a mutable copy for sorting, to not affect filteredCards if it's masterStoryCards itself
    let sortedCards = [...filteredCards];
    sortedCards.sort(function(a, b) {
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

    allVisibleStoryCards = sortedCards;

    // 3. Update pagination and display
    setupPaginationControls(allVisibleStoryCards.length, itemsPerPage, 'paginationControls', displayPage);
    displayPage(1, allVisibleStoryCards);
}

function filterStories() {
    updateDisplayedCards();
}

function sortStories() {
    updateDisplayedCards();
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
    sortSelect = document.getElementById('sortSelect');
    storyListContainer = document.getElementById('storyListContainer');
    paginationControls = document.getElementById('paginationControls');

    if (storyListContainer) {
        // Populate masterStoryCards with all story cards from the DOM.
        masterStoryCards = Array.from(storyListContainer.querySelectorAll('.story-card'));

        // Initial display: apply default sort and no filter.
        updateDisplayedCards();
    } else {
        // console.error("Story list container not found.");
        // Still attempt to setup pagination for an empty list if other controls might exist
        updateDisplayedCards(); // Will likely do nothing if storyListContainer is null but handles gracefully
    }

    // Add event listeners for filter and sort controls
    if (searchInput) {
        searchInput.addEventListener('keyup', filterStories);
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
