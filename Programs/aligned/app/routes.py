from app import application, classes, db

# FLASK & WEB
from flask import flash, render_template, redirect, url_for, Response, request, send_from_directory
from flask_login import current_user, login_user, login_required, logout_user

# UPLOADING & FILE PROCESSING
from werkzeug.utils import secure_filename
import os
import time
import ffmpy

# APP CODE
try:
    from process_openpose_user import process_openpose
except ImportError:
    from process_openpose_user_mock import process_openpose
    
from modeling import warrior2_label_csv
from process_label import ProcessLabel


@application.route('/index')
@application.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('poses'))
    else:
        return render_template('index.html')


@application.route('/register', methods=('GET', 'POST'))
def register():
    registration_form = classes.RegistrationForm()
    if registration_form.validate_on_submit():
        username = registration_form.username.data
        password = registration_form.password.data
        email = registration_form.email.data

        user_count = classes.User.query.filter_by(username=username).count() \
            + classes.User.query.filter_by(email=email).count()
        if user_count > 0:
            flash('Error - Existing user : ' + username + ' OR ' + email)

        else:
            user = classes.User(username, email, password)
            db.session.add(user)
            db.session.commit()
            return redirect(url_for('login'))
    return render_template('register.html', form=registration_form)


@application.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('poses'))

    login_form = classes.LogInForm()
    if login_form.validate_on_submit():
        username = login_form.username.data
        password = login_form.password.data
        # Look for it in the database.
        user = classes.User.query.filter_by(username=username).first()

        # Login and validate the user.
        if user is not None and user.check_password(password):
            login_user(user)
            return redirect(url_for('poses'))
        else:
            flash('Invalid username and password combination!')
    return render_template('login.html', form=login_form)


@application.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@application.route('/poses', methods=['GET'])
@login_required
def poses():
    return render_template('poses.html')


@application.route('/poses/<int:pose_id>', methods=['GET'])
@login_required
def pose(pose_id):
    # Define the 4 main yoga poses using actual sample videos
    poses = {
        1: {
            "name": "Warrior Pose",
            "description": "Warrior II is a foundational standing pose that strengthens the legs, opens the hips and chest, and builds stamina and concentration.",
            "benefits": "Strengthens legs, opens hips, improves balance and concentration",
            "emoji": "🧘‍♀️",
            "pose_category": "warrior",  # Matches samples/warrior folder
            "video_file": "warrior.mp4",  # Local sample video
            "video_type": "local"
        },
        2: {
            "name": "Chair Pose (Utkatasana)", 
            "description": "Chair pose is a foundational standing pose that strengthens the legs, glutes, and core while improving balance and focus.",
            "benefits": "Strengthens legs and core, improves balance, builds endurance",
            "emoji": "🪑",
            "pose_category": "chair",  # Matches samples/chair folder
            "video_file": "chair.mp4",  # Local sample video
            "video_type": "local"
        },
        3: {
            "name": "Phalakasana (Plank Pose)",
            "description": "Plank pose is a core-strengthening pose that builds stability and endurance throughout the entire body, particularly in the arms, shoulders, and core.",
            "benefits": "Core strength, arm and shoulder stability, full body conditioning",
            "emoji": "🏋️‍♀️",
            "pose_category": "plank",  # Matches samples/plank folder
            "video_file": "plank.mp4",  # Local sample video
            "video_type": "local"
        },
        4: {
            "name": "Warrior Back View",
            "description": "Warrior II from back view shows proper spine alignment and shoulder positioning for this foundational standing pose.",
            "benefits": "Demonstrates proper back alignment, shoulder positioning, and balance",
            "emoji": "🔄",
            "pose_category": "warrior_back",  # Matches samples/warrior_back folder
            "video_file": "warrior_back.mp4",  # Local sample video
            "video_type": "local"
        }
    }
    
    # Get the pose data or default to Warrior II
    pose_data = poses.get(pose_id, poses[1])
    
    return render_template('pose.html',
                           pose_name=pose_data["name"],
                           pose_desc=pose_data["description"],
                           pose_benefits=pose_data.get("benefits", ""),
                           pose_emoji=pose_data.get("emoji", "🧘‍♀️"),
                           pose_category=pose_data.get("pose_category", "warrior"),
                           video_file=pose_data.get("video_file", "warrior.mp4"),
                           video_type=pose_data.get("video_type", "local"))


@application.route('/video', methods=['POST'])
def video():
    if request.method == 'POST':
        try:
            if 'file' not in request.files:
                flash('No file uploaded')
                return redirect(url_for('poses'))
                
            file = request.files['file']
            if file.filename == '':
                flash('No file selected')
                return redirect(url_for('poses'))

            filename = secure_filename(file.filename)
            if not filename:
                filename = f"upload_{time.strftime('%Y%m%d_%H%M%S')}.webm"
                
            print(f"Processing file: {filename}")
            file_path = os.path.join(application.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            timestr = time.strftime("%Y%m%d-%H%M%S")
            # Use a temp folder in the project directory for Windows compatibility
            temp_dir = os.path.join(application.config['UPLOAD_FOLDER'], 'temp')
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)
            local_path = os.path.join(temp_dir, f"user_video_{timestr}.avi")

            try:
                ff = ffmpy.FFmpeg(inputs={file_path: None},
                                  outputs={local_path: '-q:v 0 -vcodec mjpeg -r 30'})
                ff.run()
                print("FFmpeg conversion successful")
            except Exception as e:
                print(f"FFmpeg error: {e}")
                # If FFmpeg fails, use the original file
                local_path = file_path

            # Process video with openpose (or mock) and return df
            df = process_openpose(local_path)
            
            # Run through rules-based system
            labels, values = warrior2_label_csv(df)
            
            # Convert labels to string for URL
            comma_separated = ','.join([str(int(c)) for c in labels])
            print(f"Analysis complete. Labels: {comma_separated}")
            
            return url_for('feedback', labels_str=comma_separated)
            
        except Exception as e:
            print(f"Error processing video: {e}")
            flash('Error processing video. Please try again.')
            return redirect(url_for('poses'))
            
    return redirect(url_for('poses'))

# @application.route('/audio')
# def done_audio():
#     return send_file('done.m4a',
#                      mimetype="audio/m4a",
#                      as_atachment=True,
#                      attachment_filename='done.m4a')


@application.route('/feedback/<labels_str>', methods=['GET'])
@login_required
def feedback(labels_str):
    try:
        labels = list(labels_str.split(','))
        labels = [int(float(c)) for c in labels]
        
        # Default to Warrior II for now, could be enhanced to track current pose
        pose_name = "Warrior II"
        instruction_video = "warrior.mp4"
        
        # Check if user achieved good form
        correct_count = sum(labels)
        total_count = len(labels)
        success_rate = correct_count / total_count if total_count > 0 else 0
        
        feedback_text = ProcessLabel.to_text(labels)
        return render_template('feedback.html',
                               feedback=feedback_text, 
                               pose_name=pose_name,
                               instruction_video=instruction_video,
                               success_rate=success_rate,
                               is_successful=success_rate > 0.6)
    except Exception as e:
        print(f"Error in feedback route: {e}")
        flash('Error generating feedback. Please try again.')
        return redirect(url_for('poses'))

@application.route('/test-feedback')
@login_required
def test_feedback():
    """Test route to see feedback page with sample data"""
    # Sample feedback for testing: [1, 0, 0, 1, 0, 1, 0, 0, 0, 0]
    labels_str = "1,0,0,1,0,1,0,0,0,0"
    return redirect(url_for('feedback', labels_str=labels_str))

@application.route('/camera-test')
def camera_test():
    """Camera test page to debug video issues"""
    return render_template('camera_test.html')

@application.route('/video-test')
def video_test():
    """Video test page to check if instruction videos are working"""
    return render_template('video_test.html')

@application.route('/mp4-test')
def mp4_test():
    """MP4 video test page"""
    return render_template('mp4_test.html')

@application.route('/simple-test')
def simple_test():
    """Simple test to check if video files exist"""
    import os
    from flask import url_for
    
    static_dir = os.path.join(application.root_path, 'static')
    
    html = f"""
    <h1>Simple Video Test</h1>
    <p><strong>Static directory:</strong> {static_dir}</p>
    <p><strong>Directory exists:</strong> {os.path.exists(static_dir)}</p>
    
    <h2>File Check:</h2>
    """
    
    video_files = ['warrior.mp4', 'chair.mp4', 'plank.mp4', 'warrior_back.mp4']
    
    for video_file in video_files:
        file_path = os.path.join(static_dir, video_file)
        file_exists = os.path.exists(file_path)
        file_size = os.path.getsize(file_path) if file_exists else 0
        static_url = url_for('static', filename=video_file)
        
        html += f"""
        <div style="margin: 15px 0; padding: 10px; border: 1px solid #ccc;">
            <h3>{video_file}</h3>
            <p>File exists: {'✅ YES' if file_exists else '❌ NO'}</p>
            <p>File size: {file_size:,} bytes</p>
            <p>Flask URL: <a href="{static_url}" target="_blank">{static_url}</a></p>
            
            <video width="300" height="200" controls style="border: 2px solid #000;">
                <source src="{static_url}" type="video/x-msvideo">
                <source src="{static_url}" type="video/avi">
                Video not supported
            </video>
        </div>
        """
    
    html += """
    <h2>Browser Test:</h2>
    <p>Test video (should work):</p>
    <video width="300" height="200" controls>
        <source src="https://www.w3schools.com/html/mov_bbb.mp4" type="video/mp4">
        External test video
    </video>
    
    <script>
        console.log('=== VIDEO DEBUG ===');
        document.querySelectorAll('video').forEach((video, index) => {
            video.addEventListener('loadeddata', () => {
                console.log('✅ Video ' + index + ' loaded successfully');
            });
            video.addEventListener('error', (e) => {
                console.error('❌ Video ' + index + ' failed:', e.target.error);
            });
        });
    </script>
    """
    
    return html

@application.route('/video-debug')
def video_debug():
    """Comprehensive video debugging page"""
    return render_template('video_debug.html')

@application.route('/debug-static')
def debug_static():
    """Debug static file URLs"""
    from flask import url_for
    
    html = """
    <h1>Static File Debug</h1>
    <h2>Video URLs:</h2>
    <ul>
    """
    
    video_files = ['warrior.mp4', 'chair.mp4', 'plank.mp4', 'warrior_back.mp4']
    
    for video_file in video_files:
        static_url = url_for('static', filename=video_file)
        html += f"""
        <li>
            <strong>{video_file}</strong><br>
            URL: <a href="{static_url}" target="_blank">{static_url}</a><br>
            <video width="300" height="200" controls style="margin: 10px 0;">
                <source src="{static_url}" type="video/x-msvideo">
                <source src="{static_url}" type="video/avi">
                Not supported
            </video>
        </li><br>
        """
    
    html += "</ul>"
    return html

@application.route('/test-video-links')
def test_video_links():
    """Quick test to check if video files exist and are accessible"""
    import glob
    
    static_dir = os.path.join(application.root_path, 'static')
    video_files = glob.glob(os.path.join(static_dir, '*.avi'))
    
    html = "<h1>Video Files Test</h1>"
    html += f"<p>Static directory: {static_dir}</p>"
    html += "<ul>"
    
    for video_path in video_files:
        filename = os.path.basename(video_path)
        size = os.path.getsize(video_path)
        video_url = f"/videos/{filename}"
        
        html += f"""
        <li>
            <strong>{filename}</strong> ({size:,} bytes)<br>
            <a href="{video_url}" target="_blank">Direct link: {video_url}</a><br>
            <video width="200" height="150" controls style="margin: 10px 0;">
                <source src="{video_url}" type="video/x-msvideo">
                Video not supported
            </video>
        </li><br>
        """
    
    html += "</ul>"
    html += f"<p><a href='/video-test'>Back to Video Test Page</a></p>"
    
    return html

@application.route('/status')
def status():
    """Status page showing app information"""
    return f"""
    <html>
    <head><title>YogaCue App - Status</title></head>
    <body style="font-family: Arial, sans-serif; margin: 40px; background-color: #f8f9fa;">
        <div style="max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.1);">
            <h1 style="color: #EC7C88; text-align: center;">🧘‍♀️ YogaCue App Status</h1>
            <div style="margin: 20px 0; padding: 20px; background-color: #d4edda; border-radius: 5px;">
                <h2 style="color: #155724;">✅ Application Status: RUNNING</h2>
                <p><strong>Version:</strong> Development Build</p>
                <p><strong>Database:</strong> SQLite (Ready)</p>
                <p><strong>Mock Processing:</strong> Enabled</p>
                <p><strong>Upload Directory:</strong> Configured</p>
            </div>
            
            <h3>🔗 Available Routes:</h3>
            <ul style="line-height: 1.8;">
                <li><a href="/">Home Page</a></li>
                <li><a href="/register">Register</a></li>
                <li><a href="/login">Login</a></li>
                <li><a href="/poses">Poses (requires login)</a></li>
                <li><a href="/test-feedback">Test Feedback (requires login)</a></li>
                <li><a href="/video-test">🎬 Video Test Page</a></li>
                <li><a href="/test-video-links">🔍 Test Video Links</a></li>
            </ul>
            
            <h3>📋 Quick Start:</h3>
            <ol style="line-height: 1.8;">
                <li>Create an account at <a href="/register">/register</a></li>
                <li>Login at <a href="/login">/login</a></li>
                <li>Choose a pose at <a href="/poses">/poses</a></li>
                <li>Record your pose and get feedback!</li>
            </ol>
            
            <div style="margin-top: 30px; padding: 15px; background-color: #fff3cd; border-radius: 5px;">
                <p><strong>🔧 Development Mode:</strong> Using mock pose processing for testing</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html_content


@application.route('/videos/<filename>')
def serve_video_file(filename):
    """Serve video files with proper headers for browser compatibility"""
    try:
        static_dir = os.path.join(application.root_path, 'static')
        file_path = os.path.join(static_dir, filename)
        
        print(f"Trying to serve video: {file_path}")
        
        if not os.path.exists(file_path):
            print(f"Video file not found: {file_path}")
            return f"Video file not found: {filename}", 404
            
        # Get file size for proper streaming
        file_size = os.path.getsize(file_path)
        print(f"Video file size: {file_size} bytes")
        
        # Determine MIME type based on file extension
        if filename.endswith('.avi'):
            mimetype = 'video/x-msvideo'
        elif filename.endswith('.mp4'):
            mimetype = 'video/mp4'
        elif filename.endswith('.webm'):
            mimetype = 'video/webm'
        else:
            mimetype = 'application/octet-stream'
            
        print(f"Serving video with MIME type: {mimetype}")
        
        # Send file with proper headers
        response = send_from_directory(
            static_dir, 
            filename, 
            mimetype=mimetype,
            as_attachment=False
        )
        
        # Add headers for video streaming
        response.headers['Accept-Ranges'] = 'bytes'
        response.headers['Content-Length'] = str(file_size)
        
        return response
        
    except Exception as e:
        print(f"Video serving error: {e}")
        return f"Error serving video: {str(e)}", 500
