import os
import json
import re
from typing import Optional
from datetime import datetime, timezone
from urllib.parse import urlparse

import redis
from dotenv import load_dotenv
from flask import Flask, abort, flash, jsonify, redirect, render_template, request, session, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import check_password_hash, generate_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError


load_dotenv()


def normalize_database_uri(database_uri):
    if database_uri.startswith('postgres://'):
        return database_uri.replace('postgres://', 'postgresql+psycopg://', 1)
    if database_uri.startswith('postgresql://'):
        return database_uri.replace('postgresql://', 'postgresql+psycopg://', 1)
    return database_uri

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'portfolio-demo-secret')
database_uri = normalize_database_uri(
    os.environ.get('DATABASE_URL', f"sqlite:///{os.path.join(app.root_path, 'shortly.db')}")
)

app.config['SQLALCHEMY_DATABASE_URI'] = database_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

CODE_PATTERN = re.compile(r'^[a-z0-9_-]{3,32}$')
RECENT_LINK_LIMIT = 10
CACHE_TTL_SECONDS = 3600
MAX_SESSION_CODES = 200

redis_client = None
redis_url = os.environ.get('REDIS_URL')
if redis_url:
    try:
        redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
        redis_client.ping()
    except redis.RedisError:
        redis_client = None
        redis_url = None

click_queue_name = os.environ.get('CLICK_QUEUE_NAME', 'shortly:click-events')
async_click_enabled = os.environ.get('ENABLE_ASYNC_CLICKS', 'true').lower() == 'true'

rate_limit_default = os.environ.get('RATE_LIMIT_DEFAULT', '300 per minute')
rate_limit_storage_uri = redis_url if redis_client else 'memory://'
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=rate_limit_storage_uri,
    default_limits=[rate_limit_default],
)
limiter.init_app(app)


class Link(db.Model):
    code = db.Column(db.String(32), primary_key=True)
    target_url = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    clicks = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    links = db.relationship('Link', backref='owner', lazy=True)


def normalize_url(raw_url):
    candidate = raw_url.strip()
    if not candidate:
        return None

    if '://' not in candidate:
        candidate = f'https://{candidate}'

    parsed = urlparse(candidate)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        return None

    return candidate


def format_created_at(value):
    if not value:
        return 'Recently added'
    return value.astimezone(timezone.utc).strftime('%b %d, %Y · %H:%M UTC')


def cache_key(code):
    return f'shortly:link:{code}'


def cache_link(link):
    if not redis_client:
        return

    payload = {
        'code': link.code,
        'url': link.target_url,
        'created_at': format_created_at(link.created_at),
        'clicks': int(link.clicks),
        'is_active': bool(link.is_active),
    }
    redis_client.set(cache_key(link.code), json.dumps(payload), ex=CACHE_TTL_SECONDS)


def get_cached_link(code):
    if not redis_client:
        return None

    serialized = redis_client.get(cache_key(code))
    if not serialized:
        return None

    try:
        return json.loads(serialized)
    except json.JSONDecodeError:
        redis_client.delete(cache_key(code))
        return None


def invalidate_cache(code):
    if redis_client:
        redis_client.delete(cache_key(code))


def increment_click_count(code):
    rows_updated = (
        Link.query.filter_by(code=code, is_active=True)
        .update({Link.clicks: Link.clicks + 1}, synchronize_session=False)
    )
    if rows_updated:
        db.session.commit()
        invalidate_cache(code)
        return True

    db.session.rollback()
    invalidate_cache(code)
    return False


def enqueue_click_event(code):
    if not (async_click_enabled and redis_client):
        return False

    try:
        redis_client.lpush(click_queue_name, code)
        return True
    except redis.RedisError:
        return False


def get_redirect_target(code) -> Optional[str]:
    cached_link = get_cached_link(code)
    if cached_link and cached_link.get('is_active') and cached_link.get('url'):
        return cached_link['url']

    link = Link.query.filter_by(code=code, is_active=True).first()
    if not link or not link.target_url:
        return None

    cache_link(link)
    return link.target_url


def build_link_payload(code, data):
    destination = data.get('url', '')
    parsed = urlparse(destination)
    created_at = data.get('created_at', 'Recently added')
    click_count = int(data.get('clicks', 0))

    return {
        'code': code,
        'url': destination,
        'short_url': url_for('redirect_to', code=code, _external=True),
        'display_host': parsed.netloc or 'custom link',
        'created_at': created_at,
        'clicks': click_count,
    }


def link_to_payload(link):
    return build_link_payload(
        link.code,
        {
            'url': link.target_url,
            'created_at': format_created_at(link.created_at),
            'clicks': int(link.clicks),
        },
    )


def get_recent_links(limit=RECENT_LINK_LIMIT):
    recent = (
        Link.query.filter_by(is_active=True)
        .order_by(Link.created_at.desc())
        .limit(limit)
        .all()
    )
    return [link_to_payload(link) for link in recent]


def get_user_codes():
    raw_codes = session.get('my_codes', [])
    if not isinstance(raw_codes, list):
        return []

    filtered = [code for code in raw_codes if isinstance(code, str) and CODE_PATTERN.match(code)]
    if len(filtered) != len(raw_codes):
        session['my_codes'] = filtered
    return filtered


def remember_user_code(code):
    existing_codes = get_user_codes()
    if code in existing_codes:
        return

    existing_codes.append(code)
    session['my_codes'] = existing_codes[-MAX_SESSION_CODES:]


def get_user_recent_links(user_codes, limit=RECENT_LINK_LIMIT):
    if not user_codes:
        return []

    recent = (
        Link.query.filter(Link.code.in_(user_codes), Link.is_active.is_(True))
        .order_by(Link.created_at.desc())
        .limit(limit)
        .all()
    )
    return [link_to_payload(link) for link in recent]


def get_current_user():
    user_id = session.get('user_id')
    if not isinstance(user_id, int):
        return None
    return db.session.get(User, user_id)


def get_current_scope_query(current_user=None):
    current_user = current_user or get_current_user()
    if current_user:
        return Link.query.filter_by(owner_id=current_user.id, is_active=True)

    user_codes = get_user_codes()
    if not user_codes:
        return None

    return Link.query.filter(Link.code.in_(user_codes), Link.is_active.is_(True))


def get_current_scope_links(limit=RECENT_LINK_LIMIT):
    query = get_current_scope_query()
    if not query:
        return []

    recent = query.order_by(Link.created_at.desc()).limit(limit).all()
    return [link_to_payload(link) for link in recent]


def get_current_scope_stats():
    query = get_current_scope_query()
    if not query:
        return 0, 0

    total_links, total_clicks = query.with_entities(
        func.count(Link.code),
        func.coalesce(func.sum(Link.clicks), 0),
    ).one()
    return int(total_links), int(total_clicks)


@app.context_processor
def inject_auth_context():
    return {'current_user': get_current_user()}


@app.route('/')
def index():
    recent_links = get_current_scope_links()
    total_links, total_clicks = get_current_scope_stats()

    stats = {
        'total_links': total_links,
        'portfolio_links': total_links,
        'total_clicks': total_clicks,
    }
    return render_template('index.html', recent_links=recent_links, stats=stats)


@app.route('/register', methods=['GET', 'POST'])
@limiter.limit('20 per minute')
def register():
    if request.method != 'POST':
        return render_template('register.html')

    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')

    if not email or '@' not in email or len(email) > 255:
        flash('Enter a valid email address.', 'error')
        return redirect(url_for('register'))

    if len(password) < 8:
        flash('Password must be at least 8 characters.', 'error')
        return redirect(url_for('register'))

    if password != confirm_password:
        flash('Passwords do not match.', 'error')
        return redirect(url_for('register'))

    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        flash('An account with that email already exists.', 'error')
        return redirect(url_for('register'))

    user = User(email=email, password_hash=generate_password_hash(password))
    db.session.add(user)
    db.session.commit()

    session['user_id'] = user.id
    flash('Account created. Welcome!', 'success')
    return redirect(url_for('index'))


@app.route('/login', methods=['GET', 'POST'])
@limiter.limit('30 per minute')
def login():
    if request.method != 'POST':
        return render_template('login.html')

    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')

    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password_hash, password):
        flash('Invalid email or password.', 'error')
        return redirect(url_for('login'))

    session['user_id'] = user.id
    flash('Signed in successfully.', 'success')
    return redirect(url_for('index'))


@app.route('/logout', methods=['POST'])
@limiter.limit('30 per minute')
def logout():
    session.pop('user_id', None)
    flash('Signed out.', 'success')
    return redirect(url_for('index'))


@app.route('/your-url', methods=['GET', 'POST'])
@limiter.limit('30 per minute')
def your_url():
    if request.method != 'POST':
        return redirect(url_for('index'))

    raw_code = request.form.get('code', '').strip().lower()
    raw_url = request.form.get('url', '').strip()

    if not CODE_PATTERN.match(raw_code):
        flash('Use 3-32 lowercase letters, numbers, hyphens, or underscores for the short code.', 'error')
        return redirect(url_for('index'))

    normalized_url = normalize_url(raw_url)
    if not normalized_url:
        flash('Enter a valid website address. Example: https://example.com', 'error')
        return redirect(url_for('index'))

    existing_link = Link.query.filter_by(code=raw_code).first()
    if existing_link:
        flash('That short code already exists. Try another one.', 'error')
        return redirect(url_for('index'))

    current_user = get_current_user()
    owner_id = current_user.id if current_user else None
    link = Link(code=raw_code, target_url=normalized_url, owner_id=owner_id)
    db.session.add(link)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash('That short code already exists. Try another one.', 'error')
        return redirect(url_for('index'))

    if not current_user:
        remember_user_code(raw_code)
    cache_link(link)

    flash('Short link created successfully.', 'success')
    return render_template('your-url.html', link=link_to_payload(link))


@app.route('/<string:code>')
@limiter.limit('1200 per minute')
def redirect_to(code):
    target_url = get_redirect_target(code)
    if target_url:
        if not enqueue_click_event(code):
            increment_click_count(code)
        return redirect(target_url)

    return abort(404)


@app.errorhandler(404)
def page_not_found(error):
    return render_template('page_not_found.html'), 404


@app.route('/api')
@limiter.limit('120 per minute')
def session_api():
    recent_links = get_current_scope_links(limit=100)
    return jsonify(
        {
            'count': len(recent_links),
            'links': recent_links,
        }
    )


with app.app_context():
    db.create_all()