document.addEventListener("DOMContentLoaded", () => {
    const calendarElement = document.getElementById("calendar");
    if (calendarElement && window.FullCalendar) {
        const calendar = new FullCalendar.Calendar(calendarElement, {
            initialView: "dayGridMonth",
            height: "auto",
            events: "/calendar-events",
            headerToolbar: {
                left: "prev,next today",
                center: "title",
                right: "dayGridMonth,listMonth",
            },
        });
        calendar.render();
    }

    const bookingItemsList = document.getElementById("booking-items-list");
    const addItemButton = document.getElementById("add-item-button");

    function bindBookingItemRow(row) {
        const signSelect = row.querySelector(".sign-select");
        const quantityInput = row.querySelector(".quantity-input");
        const quantityHelp = row.querySelector(".quantity-help");
        const removeButton = row.querySelector(".item-remove-button");

        if (signSelect && quantityInput && quantityHelp) {
            signSelect.addEventListener("change", () => {
                const selectedOption = signSelect.options[signSelect.selectedIndex];
                const total = Number(selectedOption?.dataset.total || 0);

                if (total > 0) {
                    quantityInput.max = String(total);
                    quantityInput.placeholder = `Maximum ${total}`;
                    quantityHelp.textContent = `This signage type has ${total} total items in inventory.`;
                } else {
                    quantityInput.removeAttribute("max");
                    quantityInput.placeholder = "";
                    quantityHelp.textContent = "Choose a signage type to set the quantity limit.";
                }
            });
        }

        if (removeButton && bookingItemsList) {
            removeButton.addEventListener("click", () => {
                if (bookingItemsList.querySelectorAll(".booking-item-row").length > 1) {
                    row.remove();
                    updateRemoveButtons();
                }
            });
        }
    }

    function updateRemoveButtons() {
        if (!bookingItemsList) {
            return;
        }

        const rows = bookingItemsList.querySelectorAll(".booking-item-row");
        rows.forEach((row) => {
            const button = row.querySelector(".item-remove-button");
            if (button) {
                button.disabled = rows.length === 1;
            }
        });
    }

    if (bookingItemsList) {
        bookingItemsList.querySelectorAll(".booking-item-row").forEach(bindBookingItemRow);
        updateRemoveButtons();
    }

    if (addItemButton && bookingItemsList) {
        addItemButton.addEventListener("click", () => {
            const firstRow = bookingItemsList.querySelector(".booking-item-row");
            if (!firstRow) {
                return;
            }

            const newRow = firstRow.cloneNode(true);
            const select = newRow.querySelector(".sign-select");
            const quantity = newRow.querySelector(".quantity-input");
            const help = newRow.querySelector(".quantity-help");

            if (select) {
                select.selectedIndex = 0;
            }
            if (quantity) {
                quantity.value = "";
                quantity.placeholder = "";
                quantity.removeAttribute("max");
            }
            if (help) {
                help.textContent = "Choose a signage type to set the quantity limit.";
            }

            bookingItemsList.appendChild(newRow);
            bindBookingItemRow(newRow);
            updateRemoveButtons();
        });
    }
});
