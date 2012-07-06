from __future__ import absolute_import
import logging
import layer_cache

from google.appengine.ext import db

from exercise_models import Exercise
from video_models import Video

COMMON_CORE_SEPARATOR = '.'
COMMON_CORE_BASE_URL = 'http://www.corestandards.org/the-standards/mathematics/'
COMMON_CORE_GRADE_URLS = {
        "K": "kindergarten/",
        "0": "kindergarten/",
        "1": "grade-1/",
        "2": "grade-2/",
        "3": "grade-3/",
        "4": "grade-4/",
        "5": "grade-5/",
        "6": "grade-6/",
        "7": "grade-7/",
        "8": "grade-8/",
        "9-12": ""
    }

COMMON_CORE_DOMAIN_URLS = {
        "A-APR": "high-school-algebra/arithmetic-with-polynomials-and-rational-functions/",
        "A-CED": "high-school-algebra/creating-equations/",
        "A-REI": "high-school-algebra/reasoning-with-equations-and-inequalities/",
        "A-SSE": "high-school-algebra/seeing-structure-in-expressions/",
        "CC": "counting-and-cardinality/",
        "EE": "expressions-and-equations/",
        "F": "functions/",
        "F-BF": "high-school-functions/building-functions/",
        "F-IF": "high-school-functions/interpreting-functions/",
        "F-LE": "high-school-functions/linear-quadratic-and-exponential-models/",
        "F-TF": "high-school-functions/trigonometric-functions/",
        "G": "geometry/",
        "G-C": "high-school-geometry/circles/",
        "G-CO": "high-school-geometry/congruence/",
        "G-GMD": "high-school-geometry/geometric-measurement-and-dimension/",
        "G-GPE": "high-school-geometry/expressing-geometric-properties-with-equations/",
        "G-MG": "high-school-geometry/modeling-with-geometry/",
        "G-SRT": "high-school-geometry/similarity-right-triangles-and-trigonometry/",
        "MD": "measurement-and-data/",
        "MP": "standards-for-mathematical-practice/",
        "N-CN": "hs-number-and-quantity/the-complex-number-system/",
        "N-Q": "hs-number-and-quantity/quantities/",
        "N-RN": "hs-number-and-quantity/the-real-number-system/",
        "N-VM": "hs-number-and-quantity/vector-and-matrix-quantities/",
        "NBT": "number-and-operations-in-base-ten/",
        "NF": "number-and-operations-fractions/",
        "NS": "the-number-system/",
        "OA": "operations-and-algebraic-thinking/",
        "RP": "ratios-and-proportional-relationships/",
        "S": "using-probability-to-make-decisions/",
        "S-CP": "hs-statistics-and-probability/conditional-probability-and-the-rules-of-probability/",
        "S-IC": "hs-statistics-and-probability/making-inferences-and-justifying-conclusions/",
        "S-ID": "hs-statistics-and-probability/interpreting-categorical-and-quantitative-data/",
        "S-MD": "hs-statistics-and-probability/using-probability-to-make-decisions/",
        "SP": "statistics-and-probability"
    }

COMMON_CORE_DOMAINS = {
        "A-APR": "Arithmetic with Polynomials and Rational Expressions",
        "A-CED": "Creating Equations*",
        "A-REI": "Reasoning with Equations and Inequalities",
        "A-SSE": "Seeing Structure in Expressions",
        "CC": "Counting and Cardinality",
        "EE": "Expressions and Equations",
        "F": "Functions",
        "F-BF": "Building Functions",
        "F-IF": "Interpreting Functions",
        "F-LE": "Linear, Quadratic, and Exponential Models",
        "F-TF": "Trigonometric Functions",
        "G": "Geometry",
        "G-C": "Circles",
        "G-CO": "Congruence",
        "G-GMD": "Geometric Measurement and Dimension",
        "G-GPE": "Expressing Geometric Properties with Equations",
        "G-MG": "Modeling with Geometry",
        "G-SRT": "Similarity, Right Triangles, and Trigonometry",
        "MD": "Measurement and Data",
        "MP": "Standards for Mathematical Practice",
        "N-CN": "The Complex Number System",
        "N-Q": "Quantities",
        "N-RN": "The Real Number System",
        "N-VM": "Vector and Matrix Quantities",
        "NBT": "Number and Operations in Base Ten",
        "NF": "Number and Operations--Fractions",
        "NS": "The Number System",
        "OA": "Operations and Algebraic Thinking",
        "RP": "Ratios and Proportional Relationships",
        "S": "Using Probability to Make Decisions",
        "S-CP": "Conditional Probability & the Rules of Probability",
        "S-IC": "Making Inferences and Justifying Conclusions",
        "S-ID": "Interpreting Categorical and Quantitative Data",
        "S-MD": "Using Probability to Make Decisions",
        "SP": "Statistics and Probability"
    }

class CommonCoreMap(db.Model):
    standard = db.StringProperty()
    grade = db.StringProperty()
    domain = db.StringProperty(indexed=False)
    domain_code = db.StringProperty()
    level = db.StringProperty(indexed=False)
    cc_description = db.TextProperty(indexed=False)
    cc_cluster = db.StringProperty(indexed=False)
    cc_url = db.StringProperty(indexed=False)
    exercises = db.ListProperty(db.Key, indexed=False)
    videos = db.ListProperty(db.Key, indexed=False)

    def get_entry(self, lightweight=False):
        entry = {}
        entry['standard'] = self.standard
        entry['grade'] = self.grade
        entry['domain'] = self.domain
        entry['domain_code'] = self.domain_code
        entry['level'] = self.level
        entry['cc_description'] = self.cc_description
        entry['cc_cluster'] = self.cc_cluster
        entry['cc_url'] = self.cc_url
        entry['exercises'] = []
        entry['videos'] = []
        for key in self.exercises:
            if lightweight:
                ex = db.get(key)
                entry['exercises'].append({ "display_name": ex.display_name, "ka_url": ex.ka_url })
            else:
                entry['exercises'].append(db.get(key))
        for key in self.videos:
            if lightweight:
                v = db.get(key)
                entry['videos'].append({ "title": v.title, "ka_url": v.ka_url })
            else:
                entry['videos'].append(db.get(key))

        return entry

    @staticmethod
    def get_all(lightweight=False, structured=False):
        if structured:
            return CommonCoreMap.get_all_structured(lightweight)

        query = CommonCoreMap.all()
        all_entries = []
        for e in query:
            all_entries.append(e.get_entry(lightweight=lightweight))
        return all_entries

    @staticmethod
    @layer_cache.cache_with_key_fxn(
        key_fxn=lambda lightweight: "structured_cc:%s" % lightweight,
        layer=layer_cache.Layers.Memcache)
    def get_all_structured(lightweight=False):
        all_entries = [
                { 'grade': 'K', 'domains': [] }, { 'grade': '1', 'domains': [] }, { 'grade': '2', 'domains': [] },
                { 'grade': '3', 'domains': [] }, { 'grade': '4', 'domains': [] }, { 'grade': '5', 'domains': [] },
                { 'grade': '6', 'domains': [] }, { 'grade': '7', 'domains': [] }, { 'grade': '8', 'domains': [] },
                { 'grade': '9-12', 'domains': [] }
        ]
        domains_dict = {}
        standards_dict = {}
        exercise_cache = {}
        video_cache = {}

        query = CommonCoreMap.all()
        for e in query:
            grade = (x for x in all_entries if x['grade'] == e.grade).next()

            dkey = e.grade + '.' + e.domain_code
            if dkey not in domains_dict:
                domain = {}
                domain['domain_code'] = e.domain_code
                domain['domain'] = COMMON_CORE_DOMAINS[e.domain_code]
                domain['standards'] = []
                grade['domains'].append(domain)
                domains_dict[dkey] = domain
            else:
                domain = domains_dict[dkey]

            if e.standard not in standards_dict:
                standard = {}
                standard['standard'] = e.standard
                standard['cc_url'] = e.cc_url
                standard['cc_description'] = e.cc_description
                standard['cc_cluster'] = e.cc_cluster
                standard['exercises'] = []
                standard['videos'] = []
                domain['standards'].append(standard)
                standards_dict[e.standard] = standard
            else:
                standard = standards_dict[e.standard]

            for key in e.exercises:
                if key not in exercise_cache:
                    ex = db.get(key)
                    exercise_cache[key] = ex
                else:
                    ex = exercise_cache[key]

                if lightweight:
                    standard['exercises'].append({
                        'display_name': ex.display_name,
                        'ka_url': ex.ka_url
                    })
                else:
                    standard['exercises'].append(ex)

            for key in e.videos:
                if key not in video_cache:
                    v = db.get(key)
                    video_cache[key] = v
                else:
                    v = video_cache[key]

                if lightweight:
                    standard['videos'].append({
                        'title': v.title,
                        'ka_url': v.ka_url
                    })
                else:
                    standard['videos'].append(v)

        for x in all_entries:
            if x['grade'] == '0':
                x['grade'] = 'K'

            x['domains'] = sorted(x['domains'], key=lambda k: k['domain'])
            for y in x['domains']:
                y['standards'] = sorted(y['standards'], key=lambda k: k['standard'])

        return all_entries


    def update_standard(self, standard, cluster, description):
        self.standard = standard
        self.cc_cluster = cluster
        self.cc_description = description
        cc_components = self.standard.split(COMMON_CORE_SEPARATOR)
        self.grade = cc_components[0]
        self.domain = COMMON_CORE_DOMAINS[cc_components[1]]
        self.domain_code = cc_components[1]
        self.level = cc_components[2]
        if len(cc_components) == 4:
            self.level += "." + cc_components[3]
        self.cc_url = COMMON_CORE_BASE_URL + COMMON_CORE_GRADE_URLS[self.grade] + COMMON_CORE_DOMAIN_URLS[self.domain_code] + "#"
        if self.grade != "9-12":
            self.cc_url += self.grade.lower() + "-"
        self.cc_url += self.domain_code.lower() + "-" + self.level.split('.')[0]

        return

    def update_exercise(self, exercise_name):
        ex = Exercise.all().filter('name =', exercise_name).get()
        if ex is not None:
            if ex.key() not in self.exercises:
                self.exercises.append(ex.key())
        else:
            logging.info("Exercise %s not in datastore" % exercise_name)

        return

    def update_video(self, video_youtube_id):
        v = Video.all().filter('youtube_id =', video_youtube_id).get()
        if v is not None:
            if v.key() not in self.videos:
                self.videos.append(v.key())
        else:
            logging.info("Youtube ID %s not in datastore" % video_youtube_id)

        return
