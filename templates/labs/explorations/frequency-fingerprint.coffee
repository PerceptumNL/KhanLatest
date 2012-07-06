$ ->
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("")

    # Draw Chart
    chartOptions =
        chart:
            renderTo: 'chart'
            type:     'column'
        colors: ['#3366cc']
        credits:
            enabled: no
        legend:
            enabled: no
        series: [
            data: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        ]
        title:
            text: ''
        tooltip:
            formatter: -> "#{@x}: #{@y}"
        xAxis:
            categories: alphabet
        yAxis:
            allowDecimals: no
            title:
                text: ''

    window.chart = new Highcharts.Chart(chartOptions)

    $('textarea').on 'keyup', (event) ->
        # Update Chart
        data = for letter in alphabet
            match = @value.match(new RegExp(letter, 'gi'))
            match?.length or 0

        maxLetterCount = Math.max.apply(Math, data)

        while data.indexOf(maxLetterCount) isnt -1
            data[data.indexOf(maxLetterCount)] = {color: '#dc3912', y: maxLetterCount}

        window.chart.series[0].setData(data)
