LETTERS = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z']

shifts = []

$(->
    defaultOptions = {
        chart: {
            animation: no
            type:      'column'
        }

        colors: ['#3366cc']

        credits: {
            enabled: no
        }

        legend: {
            enabled: no
        }

        series: [
            {data: 0 for letter in LETTERS}
        ]

        title: {
            text: ''
        }

        tooltip: {
            formatter: ->
                return @x + ': ' + @y
        }

        xAxis: {
            labels: {
                style: {
                    fontSize: "9px"
                }
            }
        }

        yAxis: {
            allowDecimals: no

            title: {
                text: ''
            }
        }
    }

    chart1Options = $.extend(yes, {}, defaultOptions, {
        chart: {
            renderTo: 'chart1'
        }

        xAxis: {
            categories: letter.toUpperCase() for letter in LETTERS
        }
    })

    chart1 = new Highcharts.Chart(chart1Options)

    chart2Options = $.extend(yes, {}, defaultOptions, {
        chart: {
            renderTo: 'chart2'
        }

        xAxis: {
            categories: i + 1 for char, i in LETTERS
        }
    })

    chart2 = new Highcharts.Chart(chart2Options)

    chart3Options = $.extend(yes, {}, defaultOptions, {
        chart: {
            renderTo: 'chart3'
        }

        xAxis: {
            categories: letter.toUpperCase() for letter in LETTERS
        }
    })

    chart3 = new Highcharts.Chart(chart3Options)

    updateCharts = (value) ->
        if value is ''
            value = ' '

        ciphertext            = ''
        ciphertextLetterCount = (0 for letter in LETTERS)
        plaintext             = ''
        plaintextLetterCount  = (0 for letter in LETTERS)
        randomShifts          = []
        shiftCount            = (0 for letter in LETTERS)
        shiftIndex            = 0

        for char in value
            letterIndex  = LETTERS.indexOf(char.toLowerCase())
            plaintext   += char

            if letterIndex is -1
                ciphertext += char

                randomShifts.push(' ')
            else
                while shifts.length - shiftIndex < 1
                    shifts.push(Math.floor(Math.random() * 26) + 1)

                shift = shifts[shiftIndex]

                ciphertextLetterIndex                         = (letterIndex + shift) % 26
                ciphertext                                   += LETTERS[ciphertextLetterIndex]
                ciphertextLetterCount[ciphertextLetterIndex] += 1

                plaintextLetterCount[letterIndex] += 1

                randomShifts.push(shift)
                shiftCount[shift - 1] += 1

                shiftIndex += 1

        ciphertext = ciphertext.toUpperCase()

        while shifts.length > shiftIndex
            shifts.pop()

        # Update plaintext/random shift/ciphertext.
        html = '<div id="chars">'

        for char, i in plaintext
            if char is ' '
                ciphertextChar  = '&nbsp;'
                plaintextChar   = '&nbsp;'
                randomShiftChar = '&nbsp;'
            else
                ciphertextChar  = ciphertext[i]
                plaintextChar   = char
                randomShiftChar = randomShifts[i]

            html += """
                    <div class="column">
                        <div>#{plaintextChar}</div>
                        <div style="border-bottom:1px solid;">#{randomShiftChar}</div>
                        <div>#{ciphertextChar}</div>
                    </div>
                    """

        html += '</div>'

        $('#chars').replaceWith(html)
        chars = $('#chars')
        chars.scrollLeft(chars[0].scrollWidth)

        max = Math.max.apply(Math, ciphertextLetterCount.concat(plaintextLetterCount, shiftCount))

        # Update chart 1.
        chart1.yAxis[0].setExtremes(0, max, no)
        chart1.series[0].setData(plaintextLetterCount)

        # Update chart 2.
        chart2.yAxis[0].setExtremes(0, max, no)
        chart2.series[0].setData(shiftCount)

        # Update chart 3.
        chart3.yAxis[0].setExtremes(0, max, no)
        chart3.series[0].setData(ciphertextLetterCount)

    timeout = null

    $('textarea').on('keyup', ->
        clearTimeout(timeout)

        timeout = setTimeout(
            => updateCharts(@value)
            150
        )
    )
)
