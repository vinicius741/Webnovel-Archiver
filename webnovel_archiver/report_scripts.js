// Global variables
// let currentPage = 1; // Removed pagination
// const itemsPerPage = 25; // Removed pagination
let masterStoryCards = []; // Holds all story cards, never changes after load
let allVisibleStoryCards = []; // Holds currently visible/filtered/sorted cards

// DOM Element caching (populated in DOMContentLoaded)
let searchInput = null;
let sortSelect = null;
let storyListContainer = null;
// let paginationControls = null; // Removed pagination

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

// Removed function displayPage(pageNumber, currentItems)
// Removed function updatePaginationControlsUI(totalItemsCount)
// Removed function setupPaginationControls(totalItemsCount, itemsPerPage, containerId, displayFnForPageChange)
// Removed function handlePageChange(newPage, totalItems, displayFn)

function updateDisplayedCards() {
    if (!searchInput || !sortSelect || !storyListContainer) {
        // console.warn("updateDisplayedCards called before DOM elements are cached.");
        return;
    }

    // Hide all master cards initially to ensure a clean slate
    if (masterStoryCards && masterStoryCards.length > 0) {
        masterStoryCards.forEach(card => {
            card.style.display = 'none'; // Hide all cards initially
        });
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
                valA = (a.dataset.title || '').trim().toLowerCase();
                valB = (b.dataset.title || '').trim().toLowerCase();
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

    // 3. Display all filtered and sorted cards
    // All masterStoryCards were hidden at the start of this function.
    // Now, make the cards in allVisibleStoryCards visible.
    if (allVisibleStoryCards && allVisibleStoryCards.length > 0) {
        allVisibleStoryCards.forEach(card => {
            card.style.display = 'flex'; // Assuming 'flex' is the default display for visible cards
        });
    }
    // If allVisibleStoryCards is empty, no cards will be shown, which is correct.
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
    // paginationControls = document.getElementById('paginationControls'); // Removed pagination

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
