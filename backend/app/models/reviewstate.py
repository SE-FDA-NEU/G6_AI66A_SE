import enum

class ReviewState(str, enum.Enum):
    CONFIRMED = "confirmed"
    NEEDS_REVIEW = "needs_review"
