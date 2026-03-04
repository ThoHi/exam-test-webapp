from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import json
from datetime import datetime
from flask import Response
import csv
import io

app = Flask(__name__)
app.config['SECRET_KEY'] = 'change-this-secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///exam.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'admin', 'teacher', 'student'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Exam(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    time_limit = db.Column(db.Integer, default=0)  # minutes, 0 = no limit
    questions = db.relationship('Question', backref='exam', cascade='all, delete-orphan')

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exam.id'), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    text = db.Column(db.Text, nullable=False)
    options = db.Column(db.Text)  # JSON list for single/multiple
    answer = db.Column(db.Text)   # text or JSON list for correct answers

class Grade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    exam_id = db.Column(db.Integer, db.ForeignKey('exam.id'), nullable=False)
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime)
    score = db.Column(db.Float)
    answers = db.Column(db.Text)  # JSON serialized answers
    student = db.relationship('User', backref='grades')
    exam = db.relationship('Exam', backref='grades')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ensure database and default admin
# Flask 3 removed before_first_request decorator, initialize manually

def initialize_db():
    db.create_all()
    if not User.query.filter_by(role='admin').first():
        admin = User(username='admin', role='admin')
        admin.set_password('admin')
        db.session.add(admin)
        db.session.commit()
        print('Created default admin with username "admin" and password "admin"')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Logged in successfully.', 'success')
            return redirect(url_for('index'))
        flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    # redirect based on role
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif current_user.role == 'teacher':
        return redirect(url_for('teacher_dashboard'))
    elif current_user.role == 'student':
        exams = Exam.query.all()
        return render_template('student_exams.html', exams=exams)
    else:
        return 'Unknown role', 403

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return 'Forbidden', 403
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        if User.query.filter_by(username=username).first():
            flash('User already exists', 'warning')
        else:
            user = User(username=username, role=role)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash(f'Created {role} {username}', 'success')
    users = User.query.all()
    return render_template('admin.html', users=users)

@app.route('/admin/deleteuser/<int:user_id>')
@login_required
def delete_user(user_id):
    if current_user.role != 'admin':
        return 'Forbidden', 403
    user = User.query.get_or_404(user_id)
    if user.username == 'admin':
        flash('Cannot delete default admin', 'danger')
    else:
        try:
            # remove dependent grades first to avoid FK constraint errors
            Grade.query.filter_by(student_id=user.id).delete()
            db.session.flush()  # ensure grades are deleted from db
            db.session.delete(user)
            db.session.commit()
            flash(f'User {user.username} deleted', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error deleting user: {str(e)}', 'danger')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/change-password', methods=['GET', 'POST'])
@login_required
def change_admin_password():
    if current_user.role != 'admin':
        return 'Forbidden', 403
    if request.method == 'POST':
        old_password = request.form['old_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        if not current_user.check_password(old_password):
            flash('Old password is incorrect', 'danger')
        elif new_password != confirm_password:
            flash('New passwords do not match', 'danger')
        elif len(new_password) < 6:
            flash('Password must be at least 6 characters', 'danger')
        else:
            current_user.set_password(new_password)
            db.session.commit()
            flash('Password changed successfully', 'success')
            return redirect(url_for('admin_dashboard'))
    return render_template('change_password.html')

@app.route('/teacher', methods=['GET', 'POST'])
@login_required
def teacher_dashboard():
    if current_user.role != 'teacher':
        return 'Forbidden', 403
    if request.method == 'POST':
        title = request.form['title']
        time_limit = request.form.get('time_limit', type=int) or 0
        exam = Exam(title=title, time_limit=time_limit)
        db.session.add(exam)
        db.session.commit()
        flash('Exam created', 'success')
    exams = Exam.query.all()
    # compute summary stats
    summaries = []
    for e in exams:
        grades = Grade.query.filter_by(exam_id=e.id).all()
        count = len(grades)
        avg = sum(g.score for g in grades if g.score is not None)/count if count>0 else None
        summaries.append({'exam': e, 'count': count, 'avg': avg})
    return render_template('teacher.html', summaries=summaries)

@app.route('/teacher/exam/<int:exam_id>', methods=['GET', 'POST'])
@login_required
def teacher_edit_exam(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    if request.method == 'POST':
        if 'save_exam' in request.form:
            exam.title = request.form['title']
            exam.time_limit = request.form.get('time_limit', type=int) or 0
            db.session.commit()
            flash('Exam details updated', 'success')
        else:
            qtype = request.form['type']
            text = request.form['text']
            options = request.form.get('options')
            answer = request.form.get('answer')
            q = Question(exam=exam, type=qtype, text=text)
            if options:
                q.options = json.dumps([o.strip() for o in options.split(',')])
            if answer:
                q.answer = answer
            db.session.add(q)
            db.session.commit()
            flash('Question added', 'success')
    # compute per-question stats
    stats = []
    grade_list = Grade.query.filter_by(exam_id=exam.id).all()
    for q in exam.questions:
        total_attempts = len(grade_list)
        correct_count = 0
        for g in grade_list:
            try:
                ans = json.loads(g.answers).get(f'q{q.id}', [])
            except Exception:
                ans = []
            if not isinstance(ans, list):
                ans = [ans]
            correct = None
            if q.answer:
                try:
                    correct = json.loads(q.answer)
                except Exception:
                    correct = q.answer
            if q.type == 'single' and correct and ans:
                if ans[0] == correct:
                    correct_count += 1
            elif q.type == 'multiple' and correct:
                if set(ans) == set(correct):
                    correct_count += 1
            elif q.type == 'gap' and correct:
                if ans and ans[0].strip().lower() == correct.strip().lower():
                    correct_count += 1
        stats.append({'question': q, 'total': total_attempts, 'correct': correct_count})
    return render_template('teacher_edit.html', exam=exam, stats=stats)

@app.route('/teacher/exam/<int:exam_id>/grades')
@login_required
def view_grades(exam_id):
    if current_user.role not in ['teacher', 'admin']:
        return 'Forbidden', 403
    exam = Exam.query.get_or_404(exam_id)
    grades = Grade.query.filter_by(exam_id=exam.id).all()
    return render_template('teacher_grades.html', exam=exam, grades=grades)

@app.route('/teacher/exam/<int:exam_id>/grades/export')
@login_required
def export_grades(exam_id):
    if current_user.role not in ['teacher', 'admin']:
        return 'Forbidden', 403
    exam = Exam.query.get_or_404(exam_id)
    grades = Grade.query.filter_by(exam_id=exam.id).all()
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['student','score','start_time','end_time'])
    for g in grades:
        cw.writerow([g.student.username if g.student else '', g.score, g.start_time, g.end_time])
    output = si.getvalue()
    return Response(output, mimetype='text/csv', headers={"Content-Disposition": f"attachment;filename={exam.title}_grades.csv"})

@app.route('/public/grades/<int:exam_id>.csv')
def public_grades_csv(exam_id):
    # no auth, suitable for sharing
    exam = Exam.query.get_or_404(exam_id)
    grades = Grade.query.filter_by(exam_id=exam.id).all()
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['student','score','start_time','end_time'])
    for g in grades:
        cw.writerow([g.student.username if g.student else '', g.score, g.start_time, g.end_time])
    output = si.getvalue()
    return Response(output, mimetype='text/csv', headers={"Content-Disposition": f"attachment;filename={exam.title}_grades_public.csv"})

@app.route('/student/exam/<int:exam_id>', methods=['GET', 'POST'])
@login_required
def student_take_exam(exam_id):
    if current_user.role != 'student':
        return 'Forbidden', 403
    exam = Exam.query.get_or_404(exam_id)
    # fetch or create grade entry for timing
    grade = Grade.query.filter_by(student_id=current_user.id, exam_id=exam.id, score=None).first()
    if request.method == 'GET':
        if not grade:
            grade = Grade(student_id=current_user.id, exam_id=exam.id, start_time=datetime.utcnow())
            db.session.add(grade)
            db.session.commit()
        # convert options for rendering
        for q in exam.questions:
            if q.options:
                try:
                    q.options = json.loads(q.options)
                except Exception:
                    q.options = []
        return render_template('student_exam.html', exam=exam)

    # POST submission
    answers = request.form.to_dict(flat=False)
    # basic grading: count correct singles/gaps/multiple
    score = 0
    total = 0
    for q in exam.questions:
        total += 1
        given = answers.get(f'q{q.id}', [])
        if isinstance(given, list):
            given_val = given
        else:
            given_val = [given] if given else []
        correct = None
        if q.answer:
            try:
                correct = json.loads(q.answer)
            except Exception:
                correct = q.answer
        if q.type == 'single' and correct and given_val:
            if given_val[0] == correct:
                score += 1
        elif q.type == 'multiple' and correct:
            if set(given_val) == set(correct):
                score += 1
        elif q.type == 'gap' and correct:
            if given_val and given_val[0].strip().lower() == correct.strip().lower():
                score += 1
    if grade:
        grade.end_time = datetime.utcnow()
        # check time limit
        if exam.time_limit and grade.start_time:
            elapsed = (grade.end_time - grade.start_time).total_seconds() / 60.0
            if elapsed > exam.time_limit:
                score = 0
        grade.score = score
        grade.answers = json.dumps(answers)
        db.session.commit()
    return render_template('results.html', answers=answers, total=total)

@app.route('/api/exam')
@login_required
def get_exam():
    exams = Exam.query.all()
    data = []
    for e in exams:
        qlist = []
        for q in e.questions:
            qdata = {
                'id': q.id,
                'type': q.type,
                'text': q.text
            }
            if q.options:
                qdata['options'] = json.loads(q.options)
            qlist.append(qdata)
        data.append({'id': e.id, 'title': e.title, 'questions': qlist})
    return jsonify(data)

if __name__ == '__main__':
    with app.app_context():
        initialize_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
