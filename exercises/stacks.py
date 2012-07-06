import random
import uuid

DEFAULT_CARDS_PER_STACK = 8
MAX_CARDS_PER_REVIEW_STACK = 8


class Card(object):
    """ Holds single Card's state.

    Subclassed by ProblemCard and, in the future, stuff like
    VideoCard, SurveyCard, etc. This is persisted to the datastore as
    a JSONified list in StackLog.
    """

    def __init__(self):
        self.card_type = None
        self.leaves_available = 4  # TODO(david): Is it safe to change this?
        self.leaves_earned = 0
        self.done = False


class EndOfStackCard(Card):
    """ Single Card at end of a stack that shows all sorts of
    useful end-of-stack info.
    """

    def __init__(self):
        Card.__init__(self)
        self.card_type = "endofstack"


class EndOfReviewCard(Card):
    """ Single Card at end of a review that shows info about
    review being done or not.
    """

    def __init__(self):
        Card.__init__(self)
        self.card_type = "endofreview"


class ProblemCard(Card):
    """ Holds single Card's state specific to exercise problems. """

    def __init__(self, user_exercise):
        Card.__init__(self)
        self.card_type = "problem"
        self.exercise_name = user_exercise.exercise

        if hasattr(user_exercise, 'scheduler_info'):
            self.scheduler_info = user_exercise.scheduler_info


class HappyPictureCard(Card):
    """ A surprise happy picture guaranteed to brighten any student's day. """

    # ~1 out of every N stacks will have one happy picture card
    STACK_FREQUENCY = 200

    def __init__(self):
        Card.__init__(self)
        self.card_type = "happypicture"
        self.leaves_available = 0

        # TODO: eventually this can use more pictures and be randomized
        self.src = "/images/power-mode/happy/toby.jpg"
        self.caption = "Toby the dog thinks you're awesome. Don't stop now."

    @staticmethod
    def should_include(period_multiplier=1):
        """Returns whether this card should be included in a stack.

        period_multiplier - A multiplier on the expected number of stacks for
            one of these cards to appear. Eg. if this card comes up about once
            every 200 stacks, then period_multiplier=2 would change that to
            about once every 400 stacks.
        """

        period = round(HappyPictureCard.STACK_FREQUENCY * period_multiplier)
        return random.randrange(0, int(round(period))) == 0


class Stack(object):
    """Holds the cards in this stack and has a unique identifier for logging
    purposes.

    TODO(david): Should stack_type be in this class (and with it subclasses)?
    """

    def __init__(self, cards=None):
        self.cards = cards or []
        self.uid = str(uuid.uuid4())


class ProblemStack(Stack):
    """A stack whose cards are just exercises with an occasional encouragement
    (Happy Toby card).
    """

    def __init__(self, user_exercises):
        cards = get_problem_cards(user_exercises, happy_card=True)
        Stack.__init__(self, cards)
        self.user_exercises = user_exercises


# TODO(david): This is a confusing concept and hopefully can be refactored away
#     eventually.
def get_dummy_stack(review_mode=False):
    """Returns a stack of DEFAULT_CARDS_PER_STACK filled with empty placeholder
    cards and sentinel last card.
    """

    cards = [Card() for i in xrange(0, DEFAULT_CARDS_PER_STACK)]
    last_card = EndOfReviewCard() if review_mode else EndOfStackCard()
    return Stack(cards + [last_card])


# The idea is that this will be able to return other types of cards,
# like Video cards.
def get_problem_cards(next_user_exercises, happy_card=False):
    """Returns cards corresponding to the given user exercises.

    happy_card - Whether we should possibly include a HappyPictureCard.
    """

    cards = [ProblemCard(ue) for ue in next_user_exercises]

    if happy_card:
        period_multiplier = max(1, (DEFAULT_CARDS_PER_STACK / len(cards)) - 1)
        if HappyPictureCard.should_include(period_multiplier):
            cards.insert(random.randrange(0, len(cards) + 1),
                    HappyPictureCard())

    return cards


def get_review_cards(next_user_exercises):
    review_cards = [ProblemCard(ue) for ue in next_user_exercises]

    # Cap off review stack size so it doesn't get too crazy
    return review_cards[:MAX_CARDS_PER_REVIEW_STACK]
