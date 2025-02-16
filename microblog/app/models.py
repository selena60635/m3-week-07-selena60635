from datetime import datetime, timezone
from typing import Optional
import sqlalchemy as sa
import sqlalchemy.orm as so
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from hashlib import md5
from app import db, app, login
from time import time
import jwt

followers = sa.Table(
    'followers',
    db.metadata,
    sa.Column('follower_id', sa.Integer, sa.ForeignKey('user.id'),
              primary_key=True),
    sa.Column('followed_id', sa.Integer, sa.ForeignKey('user.id'),
              primary_key=True)
)

class User(UserMixin, db.Model):
    id = sa.Column('id', sa.Integer, primary_key=True)
    username = sa.Column('username', sa.String(64), index=True, unique=True)
    email = sa.Column('email', sa.String(120),  index=True, unique=True)
    password_hash = sa.Column('password_hash', sa.String(256))
    # 印出所有我的post
    posts: so.WriteOnlyMapped['Post'] = so.relationship(
        back_populates='author')
    about_me = sa.Column('about_me', sa.String(140))
    last_seen = sa.Column('last_seen', sa.DateTime, default=lambda: datetime.now(timezone.utc))

    following: so.WriteOnlyMapped['User'] = so.relationship(
        secondary=followers, primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        back_populates='followers')
    followers: so.WriteOnlyMapped['User'] = so.relationship(
        secondary=followers, primaryjoin=(followers.c.followed_id == id),
        secondaryjoin=(followers.c.follower_id == id),
        back_populates='following')

    def __repr__(self):
        return '<User {}>'.format(self.username)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def avatar(self, size):
        digest = md5(self.email.lower().encode('utf-8')).hexdigest()
        return f'https://www.gravatar.com/avatar/{digest}?d=identicon&s={size}'
    
    def follow(self, user):
        if not self.is_following(user):
            self.following.add(user)

    def unfollow(self, user):
        if self.is_following(user):
            self.following.remove(user)

    def is_following(self, user):
        query = self.following.select().where(User.id == user.id)
        return db.session.scalar(query) is not None

    def followers_count(self):
        query = sa.select(sa.func.count()).select_from(
            self.followers.select().subquery())
        return db.session.scalar(query)

    def following_count(self):
        query = sa.select(sa.func.count()).select_from(
            self.following.select().subquery())
        return db.session.scalar(query)

    def following_posts(self):
        Author = so.aliased(User)
        Follower = so.aliased(User)
        return (
            sa.select(Post)
            .join(Post.author.of_type(Author))
            .join(Author.followers.of_type(Follower), isouter=True)
            .where(sa.or_(
                Follower.id == self.id,
                Author.id == self.id,
            ))
            .group_by(Post)
            .order_by(Post.timestamp.desc())
        )
    
    def get_reset_password_token(self, expires_in=600):
        return jwt.encode(
            {'reset_password': self.id, 'exp': time() + expires_in},
            app.config['SECRET_KEY'], algorithm='HS256')

    @staticmethod
    def verify_reset_password_token(token):
        try:
            id = jwt.decode(token, app.config['SECRET_KEY'],
                            algorithms=['HS256'])['reset_password']
        except:
            return
        return db.session.get(User, id)  
    
class Post(db.Model):
    id = sa.Column('id', sa.Integer, primary_key=True)
    body = sa.Column('body', sa.String(140))
    timestamp = sa.Column('timestamp', sa.DateTime, index=True, default=lambda: datetime.now(timezone.utc))
    user_id = sa.Column('user_id', sa.Integer, sa.ForeignKey("user.id"), index=True)
    author: so.Mapped[User] = so.relationship(back_populates='posts')

    def __repr__(self):
        return '<Post {}>'.format(self.body)



# with app.app_context():
#     db.create_all()
    
@login.user_loader
def load_user(id):
    user = db.session.scalars(sa.select(User).from_statement(sa.text(f"SELECT * FROM user WHERE id = {id}"))).first()
    return user

