import os
import hashlib

import layer_cache
from js_css_packages import templatetags
from custom_exceptions import MissingExerciseException


@layer_cache.cache_with_key_fxn(
    lambda exercise: "exercise_sha1_%s" % exercise.name,
    layer=layer_cache.Layers.InAppMemory)
def exercise_sha1(exercise):
    sha1 = None

    try:
        file_name = exercise.file_name
        # TODO(eater): remove this after adding the filename to all existing
        # exercise entities
        if not file_name or file_name == "":
            file_name = exercise.name + ".html"
        contents = raw_exercise_contents(file_name)
        sha1 = hashlib.sha1(contents).hexdigest()
    except MissingExerciseException:
        pass

    if templatetags.use_compressed_packages():
        return sha1
    else:
        return layer_cache.UncachedResult(sha1)


@layer_cache.cache_with_key_fxn(
    lambda exercise_file: "exercise_raw_html_%s" % exercise_file,
    layer=layer_cache.Layers.InAppMemory)
def raw_exercise_contents(exercise_file):
    if templatetags.use_compressed_packages():
        exercises_dir = "../khan-exercises/exercises-packed"
        safe_to_cache = True
    else:
        exercises_dir = "../khan-exercises/exercises"
        safe_to_cache = False

    path = os.path.join(os.path.dirname(__file__),
                        "%s/%s" % (exercises_dir, exercise_file))

    f = None
    contents = ""

    try:
        f = open(path)
        contents = f.read()
    except:
        raise MissingExerciseException(
                "Missing exercise file for exid '%s'" % exercise_file)
    finally:
        if f:
            f.close()

    if not len(contents):
        raise MissingExerciseException(
                "Missing exercise content for exid '%s'" % exercise_file)

    if safe_to_cache:
        return contents
    else:
        # we are displaying an unpacked exercise, either locally or in prod
        # with a querystring override. It's unsafe to cache this.
        return layer_cache.UncachedResult(contents)
