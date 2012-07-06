var ActivityGraph = {
    chart: null,
    videoMinutes: {
        type: "column",
        name: "Video Minutes",
        color: "#0080C9",
        data: [],
        defaultPoint: {
            y: 0
        }
    },
    exerciseMinutes: {
        type: "column",
        name: "Skill Minutes",
        color: "#00C9AF",
        data: [],
        defaultPoint: {
            y: 0
        }
    },
    energyPoints: {
        type: "spline",
        name: "Energy Points",
        yAxis: 1,
        marker: {enabled: false},
        color: "#C9001B",
        data: [],
        defaultPoint: {
            fEnergyPoints: true
        }
    },
    badges: {
        type: "scatter",
        name: "Badges",
        showInLegend: false,
        data: [],
        defaultPoint: {
            y: 0,
            enabled: false
        }
    },
    proficientExercises: {
        type: "scatter",
        name: "Proficient Skills",
        showInLegend: false,
        data: [],
        defaultPoint: {
            y: 0,
            enabled: false
        }
    },
    options: {
        title: "",
        credits: {
            enabled: false
        },
        chart: {
            renderTo: "highchart",
            events: {
                click: function(e) {
                    if (ActivityGraph.bucketData.enableDrillDown) {
                        if (e && e.xAxis && e.xAxis[0]) {
                            ActivityGraph.drillIntoBucket_(Math.round(e.xAxis[0].value || 0));
                        }
                    }
                }
            }
        },
        plotOptions: {
            column: {
                stacking: "normal"
            },
            scatter: {
                marker: {
                    states: {
                        hover: {
                            fillColor: "transparent",
                            lineColor: "transparent"
                        }
                    }
                }
            }
        },
        yAxis: [
            {
                title: {
                    text: "Time Spent (Minutes)",
                    style: {
                        color: "#0080C9"
                    }
                },
                labels: {
                    style: {
                        color: "#0080C9"
                    }
                },
                min: 0,
                maxPadding: 0.15,
                plotLines: [{
                    value: 0,
                    width: 1,
                    color: "#808080"
                }]
            },
            {
                title: {
                    text: "Energy Points Earned",
                    style: {
                        color: "#C9001B"
                    }
                },
                labels: {
                    style: {
                        color: "#C9001B"
                    }
                },
                plotLines: [{
                    value: 0,
                    width: 1,
                    color: "#808080"
                }],
                min: 0,
                opposite: true
            }
        ],
        legend: {
            layout: "vertical",
            align: "left",
            verticalAlign: "top",
            floating: true,
            backgroundColor: "white",
            shadow: true,
            x: 70,
            y: 5,
            itemHoverStyle: {
                cursor: "default",
                color: "#3E576F"
            }
        }
    },
    /**
     * Generate extra Highcharts fields for bars
     * Used for exercise and video minutes
     */
    generateBar_: function(info, tag) {
        if (this.bucketData.isGraphEmpty) {
            var y = Math.floor(Math.random() * 20);
            return {y: y};
        }

        if (!info) {
            return {};
        }
        return {
            y: info["minutes"],
            desc: "<strong>" + tag + "</strong> (" + info["timeSpent"] + ")<br/>" +
                info["htmlSummary"]
        };
    },

    /**
     * Generate extra Highcharts fields for splines
     * Used for energy points
     */
    generateSpline_: function(info) {
        if (this.bucketData.isGraphEmpty) {
            var lastIndex = this.videoMinutes.data.length - 1,
                minutes = this.videoMinutes.data[lastIndex].y + this.exerciseMinutes.data[lastIndex].y,
                y = minutes * 1000;
            return {y: y};
        }

        if (!info) {
            return {y: 0};
        }

        return {y: info};
    },

    /**
     * Generate extra Highcharts fields for scatter plots
     * Used for badges and proficiencies
     */
    generateScatter_: function(info, tag) {
        if (this.bucketData.isGraphEmpty) {
            if (Math.random() > 0.3) {
                return {};
            }

            var lastIndex = this.videoMinutes.data.length - 1,
                y = this.videoMinutes.data[lastIndex].y + this.exerciseMinutes.data[lastIndex].y,
                symbol = (tag === "Achievements" ?
                        "url(/images/badges/meteorite-small-chart.png)" :
                        "url(/images/node-complete-chart.png)"
                        );
            return {
                y: y,
                marker: {
                    symbol: symbol
                }
            };
        }

        if (!info) {
            return {};
        }
        var symbol = "url(/images/node-complete-chart.png)";

        if (tag === "Achievements") {
            symbol = "url(" + info["badgeUrl"] + ")";
        }

        return {
                y: info["y"],
                desc: "<strong>" + tag + "</strong><br/>" + info["htmlSummary"],
                marker: {
                    symbol: symbol
                },
                enabled: true
            };
    },

    generateAllMarks_: function(index, bucket) {
        var x = {x: index},
            extra = {};

        extra = this.generateBar_(this.bucketData.dictTopicBuckets[bucket], "Videos");
        this.videoMinutes.data.push(_.extend({}, this.videoMinutes.defaultPoint, x, extra));

        extra = this.generateBar_(this.bucketData.dictExerciseBuckets[bucket], "Skills");
        this.exerciseMinutes.data.push(_.extend({}, this.exerciseMinutes.defaultPoint, x, extra));

        extra = this.generateSpline_(this.bucketData.dictPointsBuckets[bucket]);
        this.energyPoints.data.push(_.extend({}, this.energyPoints.defaultPoint, x, extra));

        extra = this.generateScatter_(this.bucketData.dictBadgeBuckets[bucket], "Achievements");
        this.badges.data.push(_.extend({}, this.badges.defaultPoint, x, extra));

        extra = this.generateScatter_(this.bucketData.dictProficiencyBuckets[bucket], "Proficiencies");
        this.proficientExercises.data.push(_.extend({}, this.proficientExercises.defaultPoint, x, extra));
    },

    generateSeries_: function() {
        this.videoMinutes.data = [];
        this.exerciseMinutes.data = [];
        this.energyPoints.data = [];
        this.badges.data = [];
        this.proficientExercises.data = [];

        $.each(this.bucketData.bucketList, _.bind(this.generateAllMarks_, this));

        return [
                this.videoMinutes,
                this.exerciseMinutes,
                this.energyPoints,
                this.badges,
                this.proficientExercises
        ];
    },

    generateOptions_: function() {
        this.options.xAxis = {
            categories: this.bucketData.bucketList,
            labels: {
                align: "left",
                x: -5,
                y: 10,
                rotation: 45
            },
            min: 0
        };
        this.options.tooltip = {
            shared: true,
            crosshairs: true,
            formatter: function() {
                var sTitle = "<b>" + this.x + "</b>";
                s = "";
                for (var ix = 0; ix < this.points.length; ix++)
                {
                    if (this.points[ix].point.desc)
                    {
                        s += "<br/><br/>" + this.points[ix].point.desc;
                    }
                    else if (this.points[ix].point.fEnergyPoints)
                    {
                        sTitle += "<br/>" + this.points[ix].point.y + " energy points";
                    }
                }
                return sTitle + s;
            },
            enabled: !this.bucketData.isGraphEmpty
        };

        if (this.bucketData.graphTitle) {
            this.options.subtitle = {
                text: this.bucketData.graphTitle,
                x: -10
            };
        }

        if (this.bucketData.enableDrillDown) {
            this.options.plotOptions.series = {
                cursor: "pointer",
                events: {
                    legendItemClick: function() { return false; },
                    click: function(e) {
                        if (e && e.point) {
                            ActivityGraph.drillIntoBucket_(e.point.x);
                        }
                    }
                }
            };
        }
        this.options.series = this.generateSeries_();
    },

    drillIntoBucket_: function(ix) {
        if (ix == null) {
            return;
        }
        var bucket = this.chart.options.xAxis.categories[ix];
        if (bucket) {
            // TODO(benkomalo): should this use username if possible?
            Profile.loadGraph("/profile/graph/activity?email=" +
                    this.bucketData.studentEmail + "&dt_start=" + bucket);
        }
    },

    timePeriodTable_: {
        "today": {
            bucket: "hour",
            num: 24
        },
        "yesterday": {
            bucket: "hour",
            num: 24
        },
        "last-week": {
            bucket: "day",
            num: 7
        },
        "last-month": {
            bucket: "day",
            num: 30
        }
    },

    toTimeString_: function(date) {
        var hour = date.getHours(),
            minute = date.getMinutes(),
            ampm = "AM",
            hourStr = "",
            minuteStr = "";

        if (hour === 0) {
            hour = 12;
        } else if (hour > 12) {
            hour -= 12;
            ampm = "PM";
        }
        hourStr += hour;

        if (minute < 10) {
            minuteStr = "0";
        }
        minuteStr += minute;
        return hourStr + ":" + minuteStr + " " + ampm;
    },

    toDateString_: function(date) {
        return date.getFullYear() + "-" + (date.getMonth() + 1) + "-" + date.getDate();
    },

    generateFakeBuckets_: function(timePeriod) {
        var bucketData = {
                bucketList: [],
                dictBadgeBuckets: {},
                dictExerciseBuckets: {},
                dictTopicBuckets: {},
                dictPointsBuckets: {},
                dictProficiencyBuckets: {},
                enableDrillDown: false,
                isGraphEmpty: true
        }, bucketParams = this.timePeriodTable_[timePeriod],
        num = bucketParams.num,
        bucket = bucketParams.bucket,
        today = bucket === "hour" ? new Date().setHours(0, 0) : new Date();

        bucketData.bucketList = _.map(_.range(num), _.bind(function(index) {
            if (bucket === "hour") {
                var date = new Date(today);
                date.setHours(index);
                var str = this.toTimeString_(date);
                return str;
            } else {
                var date = new Date(today);
                date.setDate(today.getDate() - num + index + 1);
                var str = this.toDateString_(date);

                return str;
            }
        }, this));

        return bucketData;
    },

    render: function(bucketDataFromServer, timePeriodToFake) {
        if (bucketDataFromServer) {
            this.bucketData = bucketDataFromServer;
        } else {
            this.bucketData = this.generateFakeBuckets_(timePeriodToFake);
            if (!$("#highchart-container").length) {
                $("#graph-content").empty();
                var jelHighchartContainer = $('<div id="highchart-container" class="empty-chart"></div>'),
                    jelHighchart = $('<div id="highchart"></div>');

                $("#graph-content").append(jelHighchartContainer.append(jelHighchart));
            }
        }

        this.generateOptions_();
        this.chart = new Highcharts.Chart(this.options);

        if (bucketDataFromServer && bucketDataFromServer.isGraphEmpty) {
            Profile.showNotification("empty-graph");
        }
    }
};
