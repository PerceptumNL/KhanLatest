var ExerciseGraphOverTime = {
    options: {
        title: "",
        credits: {
            enabled: false
        },
        chart: {
            renderTo: "highchart",
            defaultSeriesType: "scatter"
        },
        plotOptions: {
            scatter: {
                cursor: "pointer",
                dashStyle: "Solid",
                lineWidth: 1
            },
            series: {
                showInLegend: false,
                marker: {
                    radius: 6
                },
                point: {
                    events: {
                        click: function() {
                            Profile.router.navigate(
                                    "/vital-statistics/problems/" + this.name,
                                    true);
                        }
                    }
                }
            }
        },
        xAxis: {
            title: {
                text: "Days working on the site"
            },
            min: 0,
            plotLines: [{
                value: 0,
                width: 1,
                color: "#808080"
            }]
        },
        yAxis: {
            title: {
                text: "Skills Completed"
            },
            plotLines: [{
                value: 0,
                width: 1,
                color: "#808080"
            }]
        },
        tooltip: {
            formatter: function() {
                    return "<b>" + this.point.display_name + "</b><br/>" + this.point.dt;
            }
        },
        legend: {
            layout: "vertical",
            align: "right",
            verticalAlign: "top",
            x: -10,
            y: 100,
            borderWidth: 0
        }
    },

    generateSeries_: function(userExercises) {
        if (!userExercises || (userExercises.length === 0)) {
            userExercises = [];
            for (var day = 1; day < 10; day++) {
                var numExercises = Math.floor(Math.random() * 5);
                for (var i = 0; i < numExercises; i++) {
                    userExercises.push({
                        daysUntilProficient: day
                    });
                }
            }
        }
        return [{
                data: _.map(userExercises, function(userExercise, index) {
                        return {
                            dt: userExercise["proficientDate"],
                            name: userExercise["name"],
                            display_name: userExercise["displayName"],
                            x: userExercise["daysUntilProficient"],
                            y: index + 1
                        };
                    })
            }];
    },

    render: function(userExercisesFromServer) {
        if (!userExercisesFromServer) {
            if (!$("#highchart-container").length) {
                $("#graph-content").empty();
                var jelHighchartContainer = $('<div id="highchart-container" class="empty-chart"></div>'),
                    jelHighchart = $('<div id="highchart"></div>');

                $("#graph-content").append(jelHighchartContainer.append(jelHighchart));
            }
        }

        this.options.series = this.generateSeries_(userExercisesFromServer);
        this.chart = new Highcharts.Chart(this.options);

        if (userExercisesFromServer && userExercisesFromServer.length === 0) {
            Profile.showNotification("empty-graph");
        }
    }
};
