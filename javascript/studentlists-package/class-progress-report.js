var ProgressReport = {

    updateFilterTimeout: null,

    studentRowView: Backbone.View.extend({
        initialize: function() {
            this.columnViews = [];
        },

        updateFilter: function(visibleColumns) {
            if (this.model.visible) {
                if (this.model.highlight && this.options.allowHighlight) {
                    $(this.el).addClass('highlight');
                } else {
                    $(this.el).removeClass('highlight');
                }

                if (this.model.hiddenCount) {
                    $(this.el).find('.hidden-students').html('(' + this.model.hiddenCount + ' hidden)');
                }

                $(this.el).show();

                $.each(this.columnViews, function(idx, columnView) {
                    columnView.updateFilter(visibleColumns, null, this.model.matchingCells);
                });
            } else {
                $(this.el).hide();
            }
        }
    }),
    studentColumnView: Backbone.View.extend({
        updateFilter: function(visibleColumns, matchingColumns, matchingCells) {
            if (visibleColumns[this.options.index]) {
                if (matchingColumns && matchingColumns[this.options.index]) {
                    $(this.el).addClass('highlight');
                } else {
                    $(this.el).removeClass('highlight');
                }

                if (matchingCells && !matchingCells[this.options.index]) {
                    $(this.el).addClass('notmatching');
                } else {
                    $(this.el).removeClass('notmatching');
                }

                $(this.el).show();
            } else {
                $(this.el).hide();
            }
        }
    }),

    init: function(model) {
        var self = this;

        this.model = model;
        this.rowViews = [];
        this.headingViews = [];
        this.hiddenStudentsModel = {
            'visible': false,
            'highlight': false,
            'hiddenCount': 10
        };

        if ($.browser.msie && parseInt($.browser.version) < 8) {
            this.showBrowserRequirements();
            return;
        }

        var adjustData = this.preAdjustTable();
        temporaryDetachElement($('#module-progress'), function() {
            this.adjustTable(adjustData);
        }, this);

        this.onResize();
        $("#module-progress td.student-module-status").hover(this.onHover, this.onUnhover);

        if (!window.fBoundProgressReport) {
            $(window).resize(ProgressReport.onResize);
            $(document).mousemove(function(e){window.mouseX = e.pageX; window.mouseY = e.pageY;});
            window.fBoundProgressReport = true;
        }

        $('#module-progress').find('th.student-exercises-col').each(function() {
            var col_idx = $(this).attr('data-id');
            self.headingViews.push(new ProgressReport.studentColumnView({
                el: this,
                model: null,
                index: col_idx
            }));
        });
        $('#module-progress').find('tr.student-email-row').each(function() {
            var row_idx = $(this).attr('data-id');
            var row = (row_idx >= 0) ? model.exercise_list[row_idx] : self.hiddenStudentsModel;
            self.rowViews.push(new ProgressReport.studentRowView({
                el: this,
                model: row,
                allowHighlight: true
            }));
        });
        $('#module-progress').find('tr.student-exercises-row').each(function() {
            var row_idx = $(this).attr('data-id');
            var row = (row_idx >= 0) ? model.exercise_list[row_idx] : self.hiddenStudentsModel;

            var rowView = new ProgressReport.studentRowView({
                el: this,
                model: row
            });
            self.rowViews.push(rowView);

            $(this).find('td.student-module-status').each(function() {
                var col_idx = $(this).attr('data-id');
                rowView.columnViews.push(new ProgressReport.studentColumnView({
                    el: this,
                    model: row,
                    index: col_idx
                }));
                $(this).click(function() {
                    // TODO: awkward turtle this should really just be a link,
                    // but I don't feel like combing through right now.
                    window.location = row.exercises[col_idx].link;
                });
            });
        });

        $("#student-progressreport-search").unbind();
        $("#student-progressreport-search").keyup(function() {
            if (ProgressReport.updateFilterTimeout == null) {
                ProgressReport.updateFilterTimeout = setTimeout(function() {
                    ProgressReport.filterRows(model);
                    ProgressReport.updateFilterTimeout = null;
                }, 250);
            }
        });

        $("input.progressreport-filter-check").unbind();
        $("input.progressreport-filter-check").change(function() { ProgressReport.filterRows(model); });
        $("#progressreport-filter-last-time").change(function() {
            $("input.progressreport-filter-check[name=\"recent\"]").attr("checked", true);
            ProgressReport.filterRows(model);
        });

        ProgressReport.filterRows(model);
    },

    filterRows: function(model) {
        var filterText = $.trim($('#student-progressreport-search').val());
        var filterList = ClassProfile.tokenizeFilterText(filterText);
        var filters = {};
        $("input.progressreport-filter-check").each(function(idx, element) {
            filters[$(element).attr('name')] = $(element).is(":checked");
        });
        var filterRecentTime = $("#progressreport-filter-last-time").val();

        var visibleColumns = [];
        var matchingColumns = [];
        var hiddenCount = 0;

        // Match columns with filter text
        $.each(model.exercise_names, function(idx, exercise) {
            matchingColumns[idx] = (filterText != '' && ClassProfile.matchText(exercise.display_name_lower, filterList));
            visibleColumns[idx] = matchingColumns[idx] || (filterText == '');
        });

        // Match rows with filter text
        $.each(model.exercise_list, function(idx, studentRow) {
            var foundMatchingExercise = false;
            var matchesFilter = ClassProfile.matchText(studentRow.nickname_lower, filterList);

            $.each(studentRow.exercises, function(idx2, exercise) {
                if (exercise.status != '' && matchingColumns[idx2]) {
                    foundMatchingExercise = true;
                    return false;
                }
            });

            if (foundMatchingExercise || matchesFilter) {

                studentRow.visible = true;
                studentRow.highlight = matchesFilter && (filterText != '');

                if (matchesFilter) {
                    $.each(studentRow.exercises, function(idx2, exercise) {
                        if (exercise.status != '')
                            visibleColumns[idx2] = true;
                    });
                }
            } else {
                studentRow.visible = false;
                hiddenCount++;
            }
        });

        // "Struggling" filter
        if (filters['struggling'] || filters['recent']) {
            var filteredColumns = [];

            // Hide students who are not struggling in one of the visible columns
            $.each(model.exercise_list, function(idx, studentRow) {
                if (studentRow.visible) {
                    var foundValid = false;
                    studentRow.matchingCells = [];
                    $.each(studentRow.exercises, function(idx2, exercise) {
                        var valid = visibleColumns[idx2];
                        if (filters['struggling'] && exercise.status != 'Struggling') {
                            valid = false;
                        } else if (filters['recent'] && exercise.seconds_since_done > 60*60*24*filterRecentTime) {
                            valid = false;
                        }
                        if (valid) {
                            studentRow.matchingCells[idx2] = true;
                            filteredColumns[idx2] = true;
                            foundValid = true;
                        } else {
                            studentRow.matchingCells[idx2] = (exercise.status == '');
                        }
                    });
                    if (!foundValid) {
                        studentRow.visible = false;
                        hiddenCount++;
                    }
                }
            });

            // Hide columns that don't match the filter
            $.each(model.exercise_names, function(idx, exercise) {
                if (!matchingColumns[idx] && !filteredColumns[idx])
                    visibleColumns[idx] = false;
            });
        } else {
            $.each(model.exercise_list, function(idx, studentRow) {
                studentRow.matchingCells = null;
            });
        }

        this.hiddenStudentsModel.visible = (hiddenCount > 0);
        this.hiddenStudentsModel.hiddenCount = hiddenCount;

        temporaryDetachElement($('#module-progress'), function() {
            _.each(this.rowViews, function(rowView) {
                rowView.updateFilter(visibleColumns);
            });
            _.each(this.headingViews, function(colView) {
                colView.updateFilter(visibleColumns, matchingColumns);
            });
        }, this);

        var adjustData = this.preAdjustTable();
        temporaryDetachElement($('#module-progress'), function() {
            this.adjustTable(adjustData);
        }, this);
    },

    showBrowserRequirements: function() {
        $("#module-progress").replaceWith("<div class='graph-notification'>Voor deze grafiek heb je een andere browser nodig zoals Google Chrome, Safari, Firefox, of Internet Explorer 8+.</div>");
    },

    hoverDiv: function() {
        if (!window.elProgressReportHoverDiv)
        {
            window.elProgressReportHoverDiv = $("<div class='exercise-info-hover' style='position:absolute;display:none;'></div>");
            $(document.body).append(window.elProgressReportHoverDiv);
        }
        return window.elProgressReportHoverDiv;
    },

    onHover: function() {
        var dtLastHover = window.dtLastHover = new Date();
        var self = this;
        setTimeout(function(){
            if (dtLastHover != window.dtLastHover) return;

            var sHover = $(self).find(".hover-content");
            if (sHover.length)
            {
                var jelHover = $(ProgressReport.hoverDiv());
                jelHover.html(sHover.html());

                var left = window.mouseX + 15;
                if (left + 150 > $(window).scrollLeft() + $(window).width()) left -= 150;

                var top = window.mouseY + 5;
                if (top + 115 > $(window).scrollTop() + $(window).height()) top -= 115;

                jelHover.css('left', left).css('top', top);
                jelHover.css('cursor', 'pointer');
                jelHover.show();
            }
        }, 100);
    },

    onUnhover: function() {
        window.dtLastHover = null;
        $(ProgressReport.hoverDiv()).hide();
    },

    onScroll: function() {

        var jelTable = $("#table_div");
        var jelHeader = $("#divHeader");
        var jelColumn = $("#firstcol");

        var leftTable = jelTable.scrollLeft();
        var topTable = jelTable.scrollTop();

        var leftHeader = jelHeader.scrollLeft(leftTable).scrollLeft();
        var topColumn = jelColumn.scrollTop(topTable).scrollTop();

        if (leftHeader < leftTable)
        {
            jelHeader.children().first().css("padding-right", 20);
            jelHeader.scrollLeft(leftTable);
        }

        if (topColumn < topTable)
        {
            jelColumn.children().first().css("padding-bottom", 20);
            jelColumn.scrollTop(topTable);
        }
    },

    onResize: function() {

        var width = $("#graph-content").width() - $("#firstTd").width() - 12;
        $(".sizeOnResize").width(width);

    },

    preAdjustTable: function() {

        var adjustData = { tableHeaderWidths: [] };

        // From http://fixed-header-using-jquery.blogspot.com/2009/05/scrollable-table-with-fixed-header-and.html
        //
        var columns = $('#divHeader th:visible');
        var colCount = columns.length-1; //get total number of column

        var m = 0;
        adjustData.brow = 'mozilla';

        jQuery.each(jQuery.browser, function(i, val) {
            if(val == true){
                adjustData.brow = i.toString();
            }
        });

        adjustData.tableDiv = $("#module-progress #table_div");
        adjustData.firstTd = $('#firstTd');
        adjustData.newFirstTdWidth = $('.tableFirstCol:visible').width();
        adjustData.tableHeaderHeight = adjustData.firstTd.height();

        $('#table_div td:visible:lt(' + colCount +')').each(function(index, element) {
            var colIdx = $(this).attr('data-id');
            var cellWidth = $(this).width();
            if (adjustData.brow == 'msie'){
                cellWidth -= 2; //In IE there is difference of 2 px
            }
            adjustData.tableHeaderWidths[colIdx] = { 'width': cellWidth };
        });

        columns.each(function(index, element){
            var colIdx = $(element).attr('data-id');
            if (colIdx) {
                if (adjustData.tableHeaderWidths[colIdx]) {
                    adjustData.tableHeaderWidths[colIdx].header = $(this).find('div.tableHeader');
                    adjustData.tableHeaderWidths[colIdx].headerTh = $(this);
                }
            }
        });

        return adjustData;
    },

    adjustTable: function(adjustData) {

        if (adjustData.brow == 'chrome' || adjustData.brow == 'safari') {
            adjustData.tableDiv.css('top', '1px');
        }

        adjustData.firstTd.css("width",adjustData.newFirstTdWidth);//for adjusting first td
        $.each(adjustData.tableHeaderWidths, function(idx, headerWidth) {
            if (headerWidth)
                if (headerWidth.width >= 0) {
                    $(headerWidth.header).width(headerWidth.width);
                    $(headerWidth.headerTh).height(adjustData.tableHeaderHeight);
                } else {
                    $(headerWidth.header).attr('style','');
                }
        });
    }
};
