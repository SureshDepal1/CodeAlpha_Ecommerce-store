const navToggle = document.querySelector(".nav-toggle");
const navLinks = document.querySelector("#primary-navigation");

if (navToggle && navLinks) {
	const closeNav = () => {
		navLinks.classList.remove("is-open");
		navToggle.classList.remove("is-open");
		navToggle.setAttribute("aria-expanded", "false");
		navToggle.setAttribute("aria-label", "Open navigation");
	};

	navToggle.addEventListener("click", () => {
		const isOpen = navLinks.classList.toggle("is-open");
		navToggle.classList.toggle("is-open", isOpen);
		navToggle.setAttribute("aria-expanded", String(isOpen));
		navToggle.setAttribute("aria-label", isOpen ? "Close navigation" : "Open navigation");
	});

	navLinks.querySelectorAll("a").forEach((link) => {
		link.addEventListener("click", closeNav);
	});


document.addEventListener("keydown", (event) => {
		if (event.key === "Escape" && navLinks.classList.contains("is-open")) {
			closeNav();
		}
	});
}
