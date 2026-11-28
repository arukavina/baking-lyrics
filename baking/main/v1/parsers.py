from flask_restx import reqparse

pagination_arguments = reqparse.RequestParser()
pagination_arguments.add_argument('page', type=int, required=False, default=1, help='Page number')
pagination_arguments.add_argument('per_page', type=int, required=False, choices=[2, 10, 20, 30, 40, 50],
                                  default=10, help='Results per page {error_msg}')


def paginate(items, page, per_page):
    """
    One page of `items`, shaped like the pagination serializer (same numbers as Flask-SQLAlchemy's
    paginate(error_out=False) used to give: a page past the end is empty, a page below 1 is page 1).
    :param items: list
    :param page: 1 based page number
    :param per_page: items per page
    :return: dict with items, page, pages, per_page and total
    """
    page = page if page and page > 0 else 1
    total = len(items)
    start = (page - 1) * per_page
    return {
        'items': items[start:start + per_page],
        'page': page,
        'pages': -(-total // per_page) if total else 0,
        'per_page': per_page,
        'total': total,
    }


def page_of(items, total, page, per_page):
    """
    A page already read by the repository, shaped like `paginate`.
    :param items: the items of this page
    :param total: total number of items
    :param page: 1 based page number (below 1 means 1)
    :param per_page: items per page
    """
    return {
        'items': items,
        'page': page if page and page > 0 else 1,
        'pages': -(-total // per_page) if total else 0,
        'per_page': per_page,
        'total': total,
    }
