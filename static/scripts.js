$(function () {
    //Autocompletion for the position
    $("#position-search").on("input", function () {
        let query = $(this).val();
        if (query.length > 1) {
            $.getJSON(`/autocomplete/position?query=${query}`, function (data) {
                // Handle autocomplete suggestions
                console.log(data); // Replace this with actual autocomplete UI handling
            });
        }
    });

    //Autocompletion for the city
    $("#city-search").on("input", function () {
        let query = $(this).val();
        if (query.length > 1) {
            $.getJSON(`/autocomplete/city?query=${query}`, function (data) {
                console.log(data); // Replace with UI handling
            });
        }
    });

    //Language switch option
    window.switchLanguage = function () {
        let language = $("#language-switch").val();
        alert(`Language switched to ${language}`);
    };
});
