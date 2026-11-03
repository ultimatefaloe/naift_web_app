from .models import Election


def election_status(request):
    return {
        "voting_is_open": Election.objects.filter(status=Election.STATUS_ONGOING).exists(),
    }
