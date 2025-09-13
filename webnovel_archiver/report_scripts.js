let masterStoryCards = [];
let searchInput = null;
let sortSelect = null;
let storyListContainer = null;
let modal = null;
let modalCloseBtn = null;
let modalBodyContent = null;

// Debounce function for search performance
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Update displayed cards with search and sort
function updateDisplayedCards() {
    if (!searchInput || !sortSelect || !storyListContainer) return;

    const filterText = searchInput.value.toLowerCase().trim();
    const sortValue = sortSelect.value;

    let filteredCards = masterStoryCards.filter((card) => {
        const title = (card.dataset.title || "").toLowerCase();
        const author = (card.dataset.author || "").toLowerCase();
        const status = (card.dataset.status || "").toLowerCase();

        return (
            title.includes(filterText) ||
            author.includes(filterText) ||
            status.includes(filterText)
        );
    });

    let sortedCards = [...filteredCards].sort((a, b) => {
        let valA, valB;
        switch (sortValue) {
            case "title":
                valA = (a.dataset.title || "").trim().toLowerCase();
                valB = (b.dataset.title || "").trim().toLowerCase();
                return valA.localeCompare(valB);
            case "author":
                valA = (a.dataset.author || "").trim().toLowerCase();
                valB = (b.dataset.author || "").trim().toLowerCase();
                return valA.localeCompare(valB);
            case "last_updated_desc":
                valA = a.dataset.lastUpdated || "";
                valB = b.dataset.lastUpdated || "";
                if (!valA && !valB) {
                    // Secondary sort by title when dates are equal
                    return (a.dataset.title || "").localeCompare(
                        b.dataset.title || ""
                    );
                }
                if (!valA) return 1;
                if (!valB) return -1;
                const dateDiff = new Date(valB) - new Date(valA);
                if (dateDiff === 0) {
                    // Secondary sort by title when dates are equal
                    return (a.dataset.title || "").localeCompare(
                        b.dataset.title || ""
                    );
                }
                return dateDiff;
            case "last_updated_asc":
                valA = a.dataset.lastUpdated || "";
                valB = b.dataset.lastUpdated || "";
                if (!valA && !valB) {
                    // Secondary sort by title when dates are equal
                    return (a.dataset.title || "").localeCompare(
                        b.dataset.title || ""
                    );
                }
                if (!valA) return 1;
                if (!valB) return -1;
                const dateDiffAsc = new Date(valA) - new Date(valB);
                if (dateDiffAsc === 0) {
                    // Secondary sort by title when dates are equal
                    return (a.dataset.title || "").localeCompare(
                        b.dataset.title || ""
                    );
                }
                return dateDiffAsc;
            case "progress_desc":
                valA = parseInt(a.dataset.progress || 0);
                valB = parseInt(b.dataset.progress || 0);
                return valB - valA;
            case "progress_asc":
                valA = parseInt(a.dataset.progress || 0);
                valB = parseInt(b.dataset.progress || 0);
                return valA - valB;
            default:
                return 0;
        }
    });

    // Clear container
    storyListContainer.innerHTML = "";

    // Add cards with animation
    sortedCards.forEach((card, index) => {
        card.style.opacity = "0";
        card.style.transform = "translateY(20px)";
        storyListContainer.appendChild(card);

        // Stagger animation
        setTimeout(() => {
            card.style.transition = "opacity 0.3s ease, transform 0.3s ease";
            card.style.opacity = "1";
            card.style.transform = "translateY(0)";
        }, index * 50);
    });

    // Update results count
    updateResultsCount(filteredCards.length);
}

// Update results count display
function updateResultsCount(count) {
    const totalCount = masterStoryCards.length;
    const subtitle = document.querySelector(".report-subtitle");
    if (subtitle) {
        const baseText = subtitle.textContent.split("•")[0];
        subtitle.textContent = `${baseText} • ${count} of ${totalCount} stories shown`;
    }
}

// Open modal with story data
function openModalWithStoryData(buttonElement) {
    if (!modal || !modalBodyContent) return;

    const storyCard = buttonElement.closest(".story-card");
    if (!storyCard) return;

    const modalContentSource = storyCard.querySelector(
        ".story-card-modal-content"
    );
    if (!modalContentSource) return;

    // Set modal content
    modalBodyContent.innerHTML = modalContentSource.innerHTML;

    // Show modal with animation
    modal.style.display = "block";
    modal.style.opacity = "0";

    setTimeout(() => {
        modal.style.opacity = "1";
        modal.querySelector(".modal-content").style.transform = "scale(1)";
    }, 10);

    // Prevent body scroll
    document.body.style.overflow = "hidden";

    // Focus management for accessibility
    modalCloseBtn.focus();
}

// Close modal
function closeModal() {
    if (!modal) return;

    modal.style.opacity = "0";
    modal.querySelector(".modal-content").style.transform = "scale(0.95)";

    setTimeout(() => {
        modal.style.display = "none";
        document.body.style.overflow = "";
        modalBodyContent.innerHTML = "";
    }, 300);
}

// Toggle synopsis expansion
function toggleSynopsis(element) {
    element.classList.toggle("expanded");
    const toggle = element.nextElementSibling;
    if (toggle && toggle.classList.contains("synopsis-toggle")) {
        toggle.textContent = element.classList.contains("expanded")
            ? "(Read less)"
            : "(Read more)";
    }
}

// Handle keyboard navigation
function handleKeyboardNavigation(event) {
    if (event.key === "Escape" && modal && modal.style.display === "block") {
        closeModal();
    }
}

// Handle touch gestures for mobile
function handleTouchGestures() {
    let startY = 0;
    let currentY = 0;

    modal.addEventListener(
        "touchstart",
        (e) => {
            startY = e.touches[0].clientY;
        },
        { passive: true }
    );

    modal.addEventListener(
        "touchmove",
        (e) => {
            currentY = e.touches[0].clientY;
            const diff = currentY - startY;

            if (diff > 50) {
                // Swipe down to close
                closeModal();
            }
        },
        { passive: true }
    );
}

// Initialize the application
function initializeApp() {
    // Get DOM elements
    searchInput = document.getElementById("searchInput");
    sortSelect = document.getElementById("sortSelect");
    storyListContainer = document.getElementById("storyListContainer");
    modal = document.getElementById("storyDetailModal");
    modalCloseBtn = document.querySelector(".modal-close-btn");
    modalBodyContent = document.getElementById("modalBodyContent");

    // Initialize story cards
    if (storyListContainer) {
        masterStoryCards = Array.from(
            storyListContainer.querySelectorAll(".story-card")
        );
        updateDisplayedCards();
    }

    // Add event listeners
    if (searchInput) {
        searchInput.addEventListener(
            "input",
            debounce(updateDisplayedCards, 300)
        );
        searchInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                searchInput.blur();
            }
        });
    }

    if (sortSelect) {
        sortSelect.addEventListener("change", updateDisplayedCards);
    }

    // Story card click handling
    if (storyListContainer) {
        storyListContainer.addEventListener("click", function (event) {
            const button = event.target.closest(".view-details-btn");
            if (button) {
                event.preventDefault();
                openModalWithStoryData(button);
            }
        });
    }

    // Modal close handling
    if (modalCloseBtn) {
        modalCloseBtn.addEventListener("click", closeModal);
    }

    if (modal) {
        // Close on backdrop click
        modal.addEventListener("click", (event) => {
            if (event.target === modal) {
                closeModal();
            }
        });

        // Add touch gesture support
        handleTouchGestures();
    }

    // Keyboard navigation
    document.addEventListener("keydown", handleKeyboardNavigation);

    // Add loading state management
    const loadingElement = document.querySelector(".loading");
    if (loadingElement) {
        loadingElement.style.display = "none";
    }

    // Add service worker for PWA capabilities (if supported)
    if ("serviceWorker" in navigator) {
        navigator.serviceWorker.register("/sw.js").catch(() => {
            // Service worker registration failed, but that's okay
        });
    }

    // Add intersection observer for lazy loading images
    if ("IntersectionObserver" in window) {
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    img.src = img.dataset.src || img.src;
                    img.classList.remove("lazy");
                    observer.unobserve(img);
                }
            });
        });

        document.querySelectorAll('img[loading="lazy"]').forEach((img) => {
            imageObserver.observe(img);
        });
    }
}

// Initialize when DOM is ready
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeApp);
} else {
    initializeApp();
}

// Export functions for global access
window.toggleSynopsis = toggleSynopsis;
window.openModalWithStoryData = openModalWithStoryData;
window.closeModal = closeModal;
