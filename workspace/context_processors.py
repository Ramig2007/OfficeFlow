
def navigation(request):
    return {"can_manage": bool(request.user.is_authenticated and request.user.can_manage)}
