$ ->
    defaultOptions =
        chart:
            animation: off
            type: 'column'
        colors: [
            '#3366cc'
            '#dc3912'
            '#ff9900'
            '#109618'
            '#990099'
            '#0099c6'
            '#dd4477'
            '#66aa00'
        ]
        credits:
            enabled: no
        legend:
            align:         'right'
            borderWidth:   0
            layout:        'vertical'
            verticalAlign: 'top'
        title:
            text: ''
        tooltip:
            formatter: -> "#{@series.name}: #{@y}"
        xAxis:
            categories: ['']
        yAxis:
            allowDecimals: no
            title:
                text: ''

    bitstrings = (length) ->
        if length == 0
            [""]
        else
            strings = []
            for head in bitstrings(length - 1)
                strings.push(head + "0")
                strings.push(head + "1")
            strings

    for length in [1..3]
        do (length) ->
            strings = bitstrings length
            regexes = (new RegExp("(?=#{s})", "g") for s in strings)

            options = $.extend true, {}, defaultOptions,
                chart:
                    renderTo: "chart#{length}"
                series:
                    {data: [0], name: s} for s in strings
            chart = new Highcharts.Chart(options)

            $("input").on "keyup", ->
                for r, i in regexes
                    count = @value.match(r)?.length or 0
                    chart.series[i].setData([count], false)
                chart.redraw()
                return
            return

    $(".btn").on "click", ->
        numbers = []
        if $(@).is('#random')
            for i in [1..1000]
                numbers.push(Math.floor(2 * Math.random()))

        $("input").val(numbers.join("")).trigger("keyup")
        return
    return
