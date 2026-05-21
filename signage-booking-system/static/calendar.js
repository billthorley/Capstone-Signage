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
    const pickupDateInput = document.getElementById("pickup-date");
    const returnDateInput = document.getElementById("return-date");
    const availabilityTable = document.getElementById("availability-table");
    let availabilityBySignId = {};

    function updateAvailabilityTableRows(items) {
        if (!availabilityTable) {
            return;
        }

        items.forEach((item) => {
            const row = availabilityTable.querySelector(`[data-sign-id="${item.id}"]`);
            if (row) {
                const availableCell = row.querySelector(".available-quantity");
                if (availableCell) {
                    availableCell.textContent = String(item.available_quantity);
                }
            }
        });
    }

    function applyAvailabilityToRow(row) {
        const signSelect = row.querySelector(".sign-select");
        const quantityInput = row.querySelector(".quantity-input");
        const quantityHelp = row.querySelector(".quantity-help");

        if (!signSelect || !quantityInput || !quantityHelp) {
            return;
        }

        const selectedOption = signSelect.options[signSelect.selectedIndex];
        const signId = signSelect.value;
        const fallbackTotal = Number(selectedOption?.dataset.total || 0);
        const signAvailability = availabilityBySignId[signId];
        const available = signAvailability ? Number(signAvailability.available_quantity) : fallbackTotal;

        if (signId && available >= 0) {
            quantityInput.max = String(available);
            quantityInput.placeholder = `Maximum ${available}`;
            quantityHelp.textContent = `Available for selected dates: ${available} of ${fallbackTotal}.`;
        } else {
            quantityInput.removeAttribute("max");
            quantityInput.placeholder = "";
            quantityHelp.textContent = "Choose a signage type to set the quantity limit.";
        }
    }

    async function refreshAvailability() {
        const params = new URLSearchParams();
        if (pickupDateInput?.value) {
            params.set("pickup_date", pickupDateInput.value);
        }
        if (returnDateInput?.value) {
            params.set("return_date", returnDateInput.value);
        }

        const url = params.toString() ? `/api/availability?${params.toString()}` : "/api/availability";

        try {
            const response = await fetch(url, { headers: { Accept: "application/json" } });
            if (!response.ok) {
                return;
            }

            const items = await response.json();
            availabilityBySignId = {};
            items.forEach((item) => {
                availabilityBySignId[String(item.id)] = item;
            });

            updateAvailabilityTableRows(items);
            if (bookingItemsList) {
                bookingItemsList.querySelectorAll(".booking-item-row").forEach(applyAvailabilityToRow);
            }
        } catch (error) {
            console.warn("Availability refresh failed", error);
        }
    }

    function bindBookingItemRow(row) {
        const signSelect = row.querySelector(".sign-select");
        const quantityInput = row.querySelector(".quantity-input");
        const quantityHelp = row.querySelector(".quantity-help");
        const removeButton = row.querySelector(".item-remove-button");

        if (signSelect && quantityInput && quantityHelp) {
            signSelect.addEventListener("change", () => {
                applyAvailabilityToRow(row);
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
        bookingItemsList.querySelectorAll(".booking-item-row").forEach(applyAvailabilityToRow);
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
            applyAvailabilityToRow(newRow);
        });
    }

    if (pickupDateInput) {
        pickupDateInput.addEventListener("change", refreshAvailability);
    }

    if (returnDateInput) {
        returnDateInput.addEventListener("change", refreshAvailability);
    }

    refreshAvailability();
});
