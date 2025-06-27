let masterStoryCards = [];
let searchInput = null;
let sortSelect = null;
let storyListContainer = null;
let modal = null;
let modalCloseBtn = null;
let modalBodyContent = null;

function updateDisplayedCards() {
    if (!searchInput || !sortSelect || !storyListContainer) return;

    const filterText = searchInput.value.toUpperCase();
    const sortValue = sortSelect.value;

    let filteredCards = masterStoryCards.filter(card => {
        const title = (card.dataset.title || '').toUpperCase();
        const author = (card.dataset.author || '').toUpperCase();
        return title.includes(filterText) || author.includes(filterText);
    });

    let sortedCards = [...filteredCards].sort((a, b) => {
        let valA, valB;
        switch (sortValue) {
            case 'title':
                valA = (a.dataset.title || '').trim().toLowerCase();
                valB = (b.dataset.title || '').trim().toLowerCase();
                return valA.localeCompare(valB);
            case 'last_updated_desc':
                valA = a.dataset.lastUpdated || '';
                valB = b.dataset.lastUpdated || '';
                return valB.localeCompare(valA);
            case 'last_updated_asc':
                valA = a.dataset.lastUpdated || '';
                valB = b.dataset.lastUpdated || '';
                return valA.localeCompare(valB);
            case 'progress_desc':
                valA = parseInt(a.dataset.progress || 0);
                valB = parseInt(b.dataset.progress || 0);
                return valB - valA;
            default:
                return 0;
        }
    });

    storyListContainer.innerHTML = '';
    sortedCards.forEach(card => storyListContainer.appendChild(card));
}

function openModalWithStoryData(buttonElement) {
    if (!modal || !modalBodyContent) return;

    const storyCard = buttonElement.closest('.story-card');
    if (!storyCard) return;

    const modalContentSource = storyCard.querySelector('.story-card-modal-content');
    if (!modalContentSource) return;

    modalBodyContent.innerHTML = modalContentSource.innerHTML;
    modal.style.display = 'block';
}

document.addEventListener('DOMContentLoaded', function() {
    searchInput = document.getElementById('searchInput');
    sortSelect = document.getElementById('sortSelect');
    storyListContainer = document.getElementById('storyListContainer');
    modal = document.getElementById('storyDetailModal');
    modalCloseBtn = document.querySelector('.modal-close-btn');
    modalBodyContent = document.getElementById('modalBodyContent');

    if (storyListContainer) {
        masterStoryCards = Array.from(storyListContainer.querySelectorAll('.story-card'));
        updateDisplayedCards();
    }

    if (searchInput) searchInput.addEventListener('keyup', updateDisplayedCards);
    if (sortSelect) sortSelect.addEventListener('change', updateDisplayedCards);

    if (storyListContainer) {
        storyListContainer.addEventListener('click', function(event) {
            const button = event.target.closest('.view-details-btn');
            if (button) openModalWithStoryData(button);
        });
    }

    if (modalCloseBtn) {
        modalCloseBtn.onclick = () => {
            modal.style.display = 'none';
            modalBodyContent.innerHTML = '';
        };
    }

    if (modal) {
        window.onclick = (event) => {
            if (event.target == modal) {
                modal.style.display = 'none';
                modalBodyContent.innerHTML = '';
            }
        };
    }
});