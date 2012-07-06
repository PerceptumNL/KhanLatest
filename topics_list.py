import copy

PLAYLIST_STRUCTURE = [
    {
        "name": "Math",
        "items":
            [
                {
                    "name": "Arithmetic",
                    "playlist": "Arithmetic"
                },
                {
                    "name": "Developmental Math",
                    "items": [
                        {
                            "name": "Developmental Math 1",
                            "playlist": "Developmental Math"
                        },
                        {
                            "name": "Developmental Math 2",
                            "playlist": "Developmental Math 2"
                        },
                        {
                            "name": "Developmental Math 3",
                            "playlist": "Developmental Math 3"
                        },
                    ]
                },
                {
                    "name": "Pre-Algebra",
                    "items": [
                        {
                            "name": "Core Pre-Algebra",
                            "playlist": "Pre-algebra"
                        },
                        {
                            "name": "Worked Examples 1",
                            "playlist": ("MA Tests for Education Licensure "
                                         "(MTEL) -Pre-Alg")
                        },
                    ]
                },
                {
                    "name": "Brain Teasers",
                    "playlist": "Brain Teasers"
                },
                {
                    "name": "Algebra",
                    "items": [
                        {
                            "name": "Core Algebra",
                            "playlist": "Algebra"
                        },
                        {
                            "name": "Worked Examples 1",
                            "playlist": "California Standards Test: Algebra I"
                        },
                        {
                            "name": "Worked Examples 2",
                            "playlist": "ck12.org Algebra 1 Examples"
                        },
                        {
                            "name": "Worked Examples 3",
                            "playlist": "California Standards Test: Algebra II"
                        },
                        {
                            "name": "Worked Examples 4",
                            "playlist": "Algebra I Worked Examples"
                        },
                    ]
                },
                {
                    "name": "Geometry",
                    "items": [
                        {
                            "name": "Core Geometry",
                            "playlist": "Geometry"
                        },
                        {
                            "name": "Worked Examples 1",
                            "playlist": "California Standards Test: Geometry"
                        },
                    ]
                },
                {
                    "name": "Trigonometry",
                    "playlist": "Trigonometry"
                },
                {
                    "name": "Probability",
                    "playlist": "Probability"
                },
                {
                    "name": "Statistics",
                    "playlist": "Statistics"
                },
                {
                    "name": "Precalculus",
                    "playlist": "Precalculus"
                },
                {
                    "name": "Calculus",
                    "playlist": "Calculus"
                },
                {
                    "name": "Differential Equations",
                    "playlist": "Differential Equations"
                },
                {
                    "name": "Linear Algebra",
                    "playlist": "Linear Algebra"
                },
            ]
    },
    {
        "name": "Science",
        "items": [
            {
                "name": "Biology",
                "playlist": "Biology"
            },
            {
                "name": "Chemistry",
                "playlist": "Chemistry"
            },
            {
                "name": "Organic Chemistry",
                "playlist": "Organic Chemistry"
            },
            {
                "name": "Healthcare and Medicine",
                "playlist": "Healthcare and Medicine"
            },
            {
                "name": "Physics",
                "playlist": "Physics"
            },
            {
                "name": "Cosmology and Astronomy",
                "playlist": "Cosmology and Astronomy"
            },
            {
                "name": "Computer Science",
                "playlist": "Computer Science"
            }
        ],
    },
    {
        "name": "Humanities & Other",
        "items": [
            {
                "name": "History",
                "playlist": "History"
            },
            {
                "name": "American Civics",
                "playlist": "American Civics"
            },
            {
                "name": "Finance",
                "items": [
                    {
                        "name": "Microeconomics",
                        "playlist": "Microeconomics"
                    },
                    {
                        "name": "Core Finance",
                        "playlist": "Finance"
                    },
                    {
                        "name": "Banking and Money",
                        "playlist": "Banking and Money"
                    },
                    {
                        "name": "Valuation and Investing",
                        "playlist": "Valuation and Investing"
                    },
                    {
                        "name": "Venture Capital and Capital Markets",
                        "playlist": "Venture Capital and Capital Markets"
                    },
                    {
                        "name": "Credit Crisis",
                        "playlist": "Credit Crisis"
                    },
                    {
                        "name": "Paulson Bailout",
                        "playlist": "Paulson Bailout"
                    },
                    {
                        "name": "Geithner Plan",
                        "playlist": "Geithner Plan"
                    },
                    {
                        "name": "Current Economics",
                        "playlist": "Current Economics"
                    },
                    {
                        "name": "Currency",
                        "playlist": "Currency"
                    },
                ],
            },
        ],
    },
    {
        "name": "Test Prep",
        "items": [
            {
                "name": "SAT Math",
                "playlist": "SAT Preparation"
            },
            {
                "name": "GMAT",
                "items": [
                    {
                        "name": "Problem Solving",
                        "playlist": "GMAT: Problem Solving"
                    },
                    {
                        "name": "Data Sufficiency",
                        "playlist": "GMAT Data Sufficiency"
                    },
                ]
            },
            {
                "name": "CAHSEE",
                "playlist": "CAHSEE Example Problems"
            },
            {
                "name": "California Standards Test",
                "items": [
                    {
                        "name": "Algebra I",
                        "playlist": "California Standards Test: Algebra I"
                    },
                    {
                        "name": "Geometry",
                        "playlist": "California Standards Test: Geometry"
                    },
                ]
            },
            {
                "name": "Competition Math",
                "playlist": "Competition Math"
            },
            {
                "name": "IIT JEE",
                "playlist": "IIT JEE Questions"
            },
            {
                "name": "Singapore Math",
                "playlist": "Singapore Math"
            },
        ],
    },
    {
        "name": "Talks and Interviews",
        "playlist": "Khan Academy-Related Talks and Interviews"
    }
]

UNCATEGORIZED_PLAYLISTS = ['New and Noteworthy']

PLAYLIST_STRUCTURE_WITH_UNCATEGORIZED = copy.deepcopy(PLAYLIST_STRUCTURE)
PLAYLIST_STRUCTURE_WITH_UNCATEGORIZED.extend([{
            "name": title,
            "playlist": title,
        } for title in UNCATEGORIZED_PLAYLISTS])

# Each DVD needs to stay under 4.4GB

DVDs_dict = {
    'Math': [  # 3.85GB
        'Arithmetic',
        'Pre-algebra',
        'Algebra',
        'Geometry',
        'Trigonometry',
        'Probability',
        'Statistics',
        'Precalculus',
    ],
    'Advanced Math': [  # 4.11GB
        'Calculus',
        'Differential Equations',
        'Linear Algebra',
    ],
    'Math Worked Examples': [  # 3.92GB
        'Developmental Math',
        'Developmental Math 2',
        'Algebra I Worked Examples',
        'ck12.org Algebra 1 Examples',
        'Singapore Math',
    ],
    'Chemistry': [  # 2.92GB
        'Chemistry',
        'Organic Chemistry',
    ],
    'Science': [  # 3.24GB
        'Cosmology and Astronomy',
        'Biology',
        'Physics',
    ],
    'Finance': [  # 2.84GB
        'Finance',
        'Banking and Money',
        'Valuation and Investing',
        'Venture Capital and Capital Markets',
        'Credit Crisis',
        'Paulson Bailout',
        'Geithner Plan',
        'Current Economics',
        'Currency',
    ],
    'Test Prep': [  # 3.37GB
        'MA Tests for Education Licensure (MTEL) -Pre-Alg',
        'California Standards Test: Algebra I',
        'California Standards Test: Algebra II',
        'California Standards Test: Geometry',
        'CAHSEE Example Problems',
        'SAT Preparation',
        'IIT JEE Questions',
        'GMAT: Problem Solving',
        'GMAT Data Sufficiency',
    ],
    'Misc': [  # 1.93GB
        'Talks and Interviews',
        'History',
        'Brain Teasers',
    ],
}

# replace None with the DVD name above that you want to burn
# this will restrict the homepage to only show the playlists from that list
DVD_list = DVDs_dict.get(None)  # 'Math'


def sorted_playlist_titles():
    playlist_titles = []
    append_playlist_titles(playlist_titles, PLAYLIST_STRUCTURE)
    playlist_titles.extend(UNCATEGORIZED_PLAYLISTS)
    return sorted(set(playlist_titles))


def append_playlist_titles(playlist_titles, obj):
    type_obj = type(obj)
    if type_obj == dict:
        if "items" in obj:
            append_playlist_titles(playlist_titles, obj["items"])
        else:
            playlist_titles.append(obj["playlist"])
    elif type_obj == list:
        for val in obj:
            append_playlist_titles(playlist_titles, val)

if DVD_list:
    topics_list = all_topics_list = DVD_list
else:
    topics_list = all_topics_list = sorted_playlist_titles()
