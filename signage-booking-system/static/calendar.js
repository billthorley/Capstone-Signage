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

    const signSelect = document.getElementById("sign-select");
    const quantityInput = document.getElementById("quantity-input");
    const quantityHelp = document.getElementById("quantity-help");

    if (signSelect && quantityInput && quantityHelp) {
        signSelect.addEventListener("change", () => {
            const selectedOption = signSelect.options[signSelect.selectedIndex];
            const total = Number(selectedOption.dataset.total || 0);

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
});
