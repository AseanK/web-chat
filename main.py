from flask import Flask, redirect, render_template, url_for, request
from flask_socketio import join_room, leave_room, send, SocketIO
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import config

app = Flask(__name__)
app.app_context().push()
app.config["SECRET_KEY"] = config.Config.SECRET_KEY

socketio = SocketIO(app)

app.config['SQLALCHEMY_DATABASE_URI'] = config.Config.DB_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Users, user_id)


class Rooms(db.Model):
    __tablename__ = "rooms"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(50), unique=True, nullable=False)
    users = relationship("Users", backref="room")
    messages = relationship("Messages", back_populates="room")

class Users(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(250), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'))
    msg = relationship("Messages", back_populates="author")

class Messages(db.Model):
    __tablename__ = "messages"
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = relationship("Users", back_populates="msg")
    room_id = db.Column(db.Integer, db.ForeignKey("rooms.id"))
    room = relationship("Rooms", back_populates="messages")

db.create_all()

@app.route('/')
def home():
    rooms = Rooms.query.all()
    return render_template("index.html", current_user=current_user, rooms=rooms)


# Register
@app.route('/register', methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if Users.query.filter_by(username=username).first():
            return render_template("register.html", error="Username alreay taken", username=username)
        else:
            new_user = Users(
                username = username,
                password = generate_password_hash(password, method='pbkdf2', salt_length=8)
            )
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for("login"))
        
    return render_template("register.html")


@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = Users.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
                login_user(user)
                return redirect(url_for("home"))
        else:
            return render_template("register.html", error="Invalid credentials", username=username)
    
    return render_template("login.html")


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for("home"))


@app.route('/create', methods=["GET", "POST"])
@login_required
def create_room():
    if request.method == "POST":
        title = request.form.get("title")
        if Rooms.query.filter_by(title=title).first():
            return render_template("create.html", error="Title alreay taken", title=title)
        else:
            new_room = Rooms(
                title = title
            )
            db.session.add(new_room)
            db.session.commit()
            return redirect(url_for("join_room", room_id=new_room.id))
    return render_template("create.html")


@app.route('/join/<int:room_id>')
@login_required
def join_room(room_id):
    requested_room = Rooms.query.filter_by(id=room_id).first()
    if not Rooms.query.filter_by(id=requested_room.id).first():
        return redirect(url_for("home", error="Invalid title"))
    
    current_user.room = requested_room
    db.session.commit()

    return redirect(url_for("chat", room_id=requested_room.id))


@app.route('/chat/<int:room_id>')
@login_required
def chat(room_id):
    requested_room = Rooms.query.filter_by(id=room_id).first()
    return render_template("chat.html", room=requested_room)


# SocketIO handle connection
@socketio.on("connect")
def connect(auth):
    room = current_user.room.id
    print(f"current room: {room}")
    if current_user.is_authenticated:
        join_room(current_user.room.id)
        send({"username": current_user.username, "message": "has entered the chat"}, room=room)
    else:
        return
    # TODO: if no users in the room, delete the room


# SocketIO handle message
@socketio.on("message")
def message(data):
    room = current_user.room.id

    # TODO: Handle time
    content = {
        "username": current_user.username,
        "message": data["data"]
    }
    send(content, to=room)
    # TODO: save the data in the database


# SocketIO handle disconnect
@socketio.on("disconnect")
def disconnect():
    room = current_user.room.id
    leave_room(room)
    # TODO: If no user in the room, delete

    send({"username": current_user.username, "message": "has left the chat"}, to=room)


if __name__ == "__main__":
    socketio.run(app, debug=True)