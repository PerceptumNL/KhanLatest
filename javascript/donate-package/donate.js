/*
 * Handle interactive elements on "Donate" page.
 */

var Donate = {

    init: function() {
        Donate.getTimePeriodRadioButton().live("click", Donate.updateTimePeriod);
        $("#donation-submit").live("click", Donate.submit);

        // Initialize the display for the selected time period.
        Donate.updateTimePeriod();
    },

    /*
     * When the user clicks a donate radio button, display or hide the recurring frequency
     * section and shift it based on whether months or years is selected.
     *
     * Some tomfoolery going on here, using a combination of visibility and display to make
     * things show up properly.
     */
    updateTimePeriod: function() {
        var rbval = Donate.getCheckedTimePeriodRadioButton().val();
        if (rbval === "O") { // "O": One-time donation
            // For a one-time donation, hide the "recurring frequency"
            // elements.
            $('#recurring-frequency-months')
                .css("visibility", "hidden")
                .css("display", "inline");
            $('#recurring-frequency-years')
                .css("display", "none");
        } else if (rbval === "M") { // "M": Monthly donation
            // For a monthly donation, show the monthly UI
            // and hide the annual UI.
            $('#recurring-frequency-months')
                .css("visibility", "visible")
                .css("display", "inline");
            $('#recurring-frequency-years')
                .css("display", "none");
        } else { // Annual donation
            // Hide the monthly UI and show the annual UI.
            $('#recurring-frequency-months')
                .css("display", "none");
            $('#recurring-frequency-years')
                .css("display", "inline");
        }
    },

    /* When the user clicks the "Donate" button, get the proper values in
     * line to send to PayPal depending on what options are checked.
     */
    submit: function(e) {
        // Disable the form's default submit action because we do it
        // as a callback from bingo.
        e.preventDefault();
        var rbval = Donate.getCheckedTimePeriodRadioButton().val();
        var amount = $('#donate-amount').val();
        var duration = "One-Time";

        if (rbval === "O") { // One-time donation
            $('#paypal-cmd').val("_donations");
            $('#paypal-item-name').val("One-time donation to Khan Academy");
        } else {
            $('#paypal-cmd').val("_xclick-subscriptions");
            $('#paypal-item-name').val("Recurring donation to Khan Academy");
            $('#paypal-recurring-amount').val(amount);
            var period = (rbval === "M" ? $('#months-repeating').val() : $('#years-repeating').val());

            // Create a string for the duration to report to MixPanel.
            duration = (period !== "0" ? period : "ongoing") + " " + (rbval === "M" ? "months" : "years");
            $('input[name=srt]').val(period);
        }
        // mixpanel.com to track people's clicking the button
        // that takes them to PayPal to make a donation.
        Analytics.trackSingleEvent("Donate-Link-Paypal",
                                    {"Amount": amount,
                                     "Duration": duration});
        // NOTE: When this bingo is turned off, we'll need to reactivate
        // the form's submit action.
        gae_bingo.bingo( "hp_donate_button_paypal", Donate.submitPaypal, Donate.submitPaypal);

    },

    submitPaypal: function() {
        $('#paypal-form').submit();
    },

    getTimePeriodRadioButton: function() {
        return $("input[name=t3]:radio");
    },

    getCheckedTimePeriodRadioButton: function() {
        return $("input[name=t3]:radio:checked");
    },
}

$(document).ready(function() {
    $("#accordion").accordion({ autoHeight: false, collapsible: true, active: false });

    Donate.init();
});
