"""Shared pagination utilities.

Django's Paginator is the workhorse, but generating "preserve all query params
except page" links and "page X of Y" UI is repeated across pages. A tiny helper
keeps templates clean.
"""

from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator


def paginate(queryset, request, per_page):
    """Return ``(page_obj, querystring_no_page, page_range)``.

    ``querystring_no_page`` is a string like ``"q=django&category=programming&"``
    ready to prepend to ``"page=N"`` in templates. Includes a trailing ``"&"``
    if non-empty so the template can write ``?{{ querystring_no_page }}page=2``
    without worrying about ampersand placement.

    ``page_range`` is a list of page numbers (with ``ELLIPSIS`` placeholders)
    pre-computed via Django's ``get_elided_page_range``. We do it here because
    Django's ``{% for %}`` tag can't call methods with arguments inline.
    """
    paginator = Paginator(queryset, per_page)
    page_number = request.GET.get("page")
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    params = request.GET.copy()
    params.pop("page", None)
    qs = params.urlencode()
    if qs:
        qs = qs + "&"

    page_range = list(
        paginator.get_elided_page_range(page_obj.number, on_each_side=1, on_ends=1)
    )

    return page_obj, qs, page_range
