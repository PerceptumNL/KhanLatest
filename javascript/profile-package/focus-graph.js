var FocusGraph = {
    star: $.browser.msie ? "*" : "★",

    generateSeries_: function() {
        var series = [];

        if (this.segmentData.totalExerciseSeconds) {
            // Exercise legend in the upper left
            var exerciseLegend = {
                type: "pie",
                name: "Skills",
                cursor: "",
                size: "20%",
                innerSize: "13%",
                center: ["11%", "14%"],
                dataLabels: {
                    connectorColor: "silver",
                    connectorWidth: 2,
                    color: "#898989"
                },
                data: [
                        {
                            name: "Skills",
                            fLegend: true,
                            y: 100,
                            color: "silver"
                        }
                ]
            };

            series.push(exerciseLegend);

            // Exercise graph in the center
            var exerciseFocus = {
                type: "pie",
                name: "Skill Focus",
                innerSize: "55%",
                size: "85%"
            };
            if (!this.segmentData.isGraphEmpty) {
                exerciseFocus.point = {
                    events: {
                        click: function() {
                            Profile.router.navigate(
                                    "/vital-statistics/problems/" + this.exid,
                                    true);
                        }
                    }
                };
            }
            exerciseFocus.data = _.map(this.segmentData.dictExerciseSeconds, function(segment, key) {
                var proficientText = segment["proficient"] ? (", <b>" + this.star + "Proficient</b>") : "",
                    tooltip = "<b>" + segment["exerciseTitle"] + "</b> (skill" + proficientText + ")";

                return {
                    name: "<b>" + segment["exerciseTitle"] + (segment["proficient"] ? " " + this.star : "") + "</b>",
                    exid: segment["exid"],
                    y: segment["percentage"],
                    tooltip_title: tooltip,
                    time_spent: segment["timeSpent"],
                    tooltip_more: segment["sProblems"] + "<br/>" + segment["sCorrectProblems"] + "<br/>"
                };
            }, this);

            series.push(exerciseFocus);
        }

        if (this.segmentData.totalTopicSeconds) {
            // Video legend in the upper left
            var videoLegend = {
                type: "pie",
                name: "Videos",
                cursor: "",
                size: "9.4%",
                innerSize: "3%",
                center: ["11%", "14%"],
                dataLabels: {
                    connectorColor: "silver",
                    connectorWidth: 2,
                    color: "#898989"
                },
                data: [
                        {
                            name: "",
                            fLegend: true,
                            y: 25,
                            visible: false,
                            color: "silver"
                        },
                        {
                            name: "Videos",
                            fLegend: true,
                            y: 75,
                            color: "silver"
                        }
                ]
            };

            series.push(videoLegend);

            // Video graph in the center
            var videoFocus = {
                type: "pie",
                cursor: "",
                name: "Video Focus",
                innerSize: "55%",
                size: "85%"
            };

            if (this.segmentData.totalExerciseSeconds) {
                // Fit the video graph inside the exercise graph
                _.extend(videoFocus, {
                    size: "40%",
                    innerSize: "10%",
                    dataLabels: {enabled: false}
                });
            }

            videoFocus.data = _.map(this.segmentData.dictTopicSeconds, function(segment, key) {
                return {
                    name: segment["playlistTitle"],
                    y: segment["percentage"],
                    tooltip_title: "<b>" + segment["playlistTitle"] + "</b> (videos)",
                    time_spent: segment["timeSpent"],
                    tooltip_more: segment["tooltipMore"]
                };
            });

            series.push(videoFocus);
        }

        return series;
    },

    options: {
        title: "",
        credits: {
            enabled: false
        },
        chart: {
            renderTo: "highchart"
        },
        plotOptions: {
            pie: {
                cursor: "pointer",
                dataLabels: {
                    enabled: true,
                    color: "black",
                    connectorColor: "black"
                }
            }
        },
        tooltip: {
            enabled: true,
            formatter: function() {
                if (this.point.fLegend) {
                    return false;
                }
                return this.point.tooltip_title + "<br/> - " + this.point.time_spent + " total<br><br>" + this.point.tooltip_more;
            }
        }
    },

    generateFakeSegments_: function() {
        var segmentData = {
            dictExerciseSeconds: {
                "unused1": {
                    exerciseTitle: "Addition 1",
                    proficient: true,
                    percentage: 3
                },
                "unused2": {
                    exerciseTitle: "Addition 2",
                    proficient: true,
                    percentage: 4
                },
                "unused3": {
                    exerciseTitle: "Multiplication 1",
                    proficient: true,
                    percentage: 10
                },
                "unused4": {
                    exerciseTitle: "Equation of a line",
                    proficient: true,
                    percentage: 10
                },
                "unused5": {
                    exerciseTitle: "Equation of a circle",
                    proficient: false,
                    percentage: 33
                },
                "unused6": {
                    exerciseTitle: "Derivative intuition",
                    proficient: true,
                    percentage: 20
                },
                "unused7": {
                    exerciseTitle: "Unit circle intuition",
                    proficient: false,
                    percentage: 10
                }
            },
            dictTopicSeconds: {
                "unused1": {
                    percentage: 32
                },
                "unused2": {
                    percentage: 10
                },
                "unused3": {
                    percentage: 46
                },
                "unused4": {
                    percentage: 12
                }
            },
            isGraphEmpty: true,
            totalExerciseSeconds: 100,
            totalTopicSeconds: 100
        };

        return segmentData;
    },

    render: function(segmentDataFromServer) {
        if (segmentDataFromServer && !segmentDataFromServer.isGraphEmpty) {
            this.segmentData = segmentDataFromServer;
        } else {
            this.segmentData = this.generateFakeSegments_();
            if (!$("#highchart-container").length) {
                $("#graph-content").empty();
                var jelHighchartContainer = $('<div id="highchart-container" class="empty-chart"></div>'),
                    jelHighchart = $('<div id="highchart"></div>');

                $("#graph-content").append(jelHighchartContainer.append(jelHighchart));
            }
        }

        this.options.series = this.generateSeries_();
        this.chart = new Highcharts.Chart(this.options);

        if (segmentDataFromServer && segmentDataFromServer.isGraphEmpty) {
            Profile.showNotification("empty-graph");
        }
    }
};
