(function () {
    // Select all rich text answers.
    const richtextanswers = document.querySelector(".rich-text--answers");

    // Remove p tags with only whitespace inside.
    const richtextanswers_paras = richtextanswers.querySelectorAll("p");
    richtextanswers_paras.forEach(function (para) {
        if (para.textContent.trim() === "") {
            para.remove();
        }
    });

    // Wrap all tables in a div so overflow auto works.
    const richtextanswers_tables = richtextanswers.querySelectorAll("table");
    richtextanswers_tables.forEach(function (table) {
        const table_wrapper = document.createElement("div");
        table_wrapper.classList.add("rich-text__table");
        table.parentNode.insertBefore(table_wrapper, table);
        table_wrapper.appendChild(table);
    });
})();
