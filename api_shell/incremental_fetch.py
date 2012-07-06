from copy import deepcopy


def incremental_fetch(query, batch_size=500):
    ''' There is a 1K limit for fetching on production.  Use this function like
    videos = incremental_fetch(Video.all()) to get around the limit'''
    i = 0
    start_key = None
    all_entities = []
    while True:
        print i
        q = deepcopy(query)
        if start_key:
            q.filter("__key__ >", start_key)
        q.order("__key__")
        entities = q.fetch(batch_size)
        if len(entities):
            all_entities.extend(entities)
            start_key = entities[-1].key()
            i += batch_size
        else:
            break
    return all_entities
