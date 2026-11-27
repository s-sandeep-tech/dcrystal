"""Shared UID-based design attachment lookup for stock report endpoints."""
from flask import request, jsonify
from urllib.parse import urlsplit


def design_image_response(get_external_db_connection, logger):
    design_uid = request.args.get('design_uid', '').strip()
    if not design_uid:
        return jsonify(message='A design UID is required.'), 400

    connection = None
    try:
        connection = get_external_db_connection()
        connection.set_session(readonly=True)
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '15s'")
            cursor.execute(
                'SELECT design_uid, design_no, thumb_file_url '
                'FROM ext_view.vw_design_attachment WHERE design_uid = %s LIMIT 1',
                (design_uid,),
            )
            row = cursor.fetchone()
        image_url = (row[2] or '').strip() if row else ''
        parsed = urlsplit(image_url)
        if image_url and not parsed.scheme:
            image_url = 'https://crystal.kalyanjewellers.company/' + image_url.lstrip('/')
        elif not image_url or parsed.scheme not in ('http', 'https') or not parsed.netloc:
            image_url = None
        response = jsonify(design_uid=design_uid, image_url=image_url)
        response.headers['Cache-Control'] = 'no-store'
        return response
    except Exception:
        logger.exception('Unable to load design image')
        return jsonify(message='Unable to load the design image. Please try again.'), 503
    finally:
        if connection is not None:
            connection.close()
