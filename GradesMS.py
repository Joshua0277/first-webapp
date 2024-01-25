from flask import Flask, jsonify, request,redirect,session, url_for,send_file
from flask_cors import CORS
import mysql.connector
from mysql.connector import Error
import os
import io
import pandas as pd
from werkzeug.utils import secure_filename

ALLOWED_MIME_TYPES = ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'application/vnd.ms-excel', 'text/csv']
EXPECTED_COLUMNS = {'Student_ID', 'Class_code', 'Score'}

app = Flask(__name__)
app.secret_key = 'up6cj8633'
CORS(app, origins="*")
@app.route('/test')
def test():
    return app.send_static_file('test.html')

@app.route('/login', methods=['POST'])
def login():
    user_ID = request.json['ID']
    password = request.json['password']
    # 这里添加验证用户名和密码的逻辑
    # 假设您已经有一个函数来验证用户名和密码
    if validate_credentials(user_ID, password):
        try:
            conn = create_connection()
            cursor = conn.cursor()
            query = """
                    (SELECT Student_ID AS ID, Student_Name AS Name FROM Student_Info WHERE Student_ID = %s)
                    UNION
                    (SELECT Professor_ID AS ID, Professor_Name AS Name FROM Professor_Info WHERE Professor_ID = %s)
            """
            cursor.execute(query, (user_ID, user_ID))
            row = cursor.fetchone()

            if row:
                user_name = row[1]  # 获取 Name 字段
                return jsonify({'success': True, 'userId': user_ID, 'userName': user_name}), 200
            else:
                return jsonify({'error': 'User not found'}), 404
        except Error as e:
            return jsonify({'error': str(e)}), 500
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()
        # 登录成功
    else:
        # 登录失败
        return jsonify({"success": False, "error": "Invalid credentials"}), 401

@app.route('/logout', methods=['POST','GET'])
def logout():
    session.pop('user_id', None)

    return jsonify({'success': True})
# 一个示例的验证函数
def validate_credentials(username, password):
    conn = None
    try:
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM User_List WHERE ID = %s AND Password = %s", (username, password,))
        user = cursor.fetchone()

        if user:
            return user[0] 
        else:
            return None
    except Error as e:
        return None
    finally:
        if conn and conn.is_connected():
            conn.close()

def create_connection():
    try:
        conn = mysql.connector.connect(
            host='localhost',
            port='3306',
            user='root',
            password='up6cj863',
            database='test1'
        )
        return conn
    except Error as e:
        error_message = f"Error while connecting to MySQL: {e}"
        print(error_message)
        return jsonify({'error': error_message}), 500

def get_user_type(user_id):
    conn = create_connection()
    if conn is not None:
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT User_Type FROM User_List WHERE ID = %s", (user_id,))
                result = cursor.fetchone()
                return result[0] if result else None
        finally:
            conn.close()
    else:
        return None

@app.route('/get-courses/<user_id>')
def get_courses(user_id):
    conn = None
    try:
        conn = create_connection()
        cursor = conn.cursor()
        user_type = get_user_type(user_id)
        if user_type is None:
            return jsonify({'error': 'User not found'}), 404

        if user_type == 'Student':
            query = """
                SELECT DISTINCT c.Class_code, c.Subject
                FROM Grade g
                JOIN Class c ON g.Class_code = c.Class_code
                WHERE g.Student_ID = %s
            """
            cursor.execute(query, (user_id,))
        elif user_type == 'TA':
            # 对于 TA，同时查询学生和 TA 的课程
            query = """
                SELECT DISTINCT c.Class_code, c.Subject
                FROM Grade g
                JOIN Class c ON g.Class_code = c.Class_code
                WHERE g.Student_ID = %s
                UNION
                SELECT Class_code, Subject
                FROM Class
                WHERE TA_ID = %s
            """
            cursor.execute(query, (user_id, user_id))
        elif user_type == 'Professor':
            query = """
                SELECT Class_code, Subject
                FROM Class
                WHERE Professor_ID = %s
            """
            cursor.execute(query, (user_id,))
        else:
            return jsonify({'error': 'Invalid user type'}), 400

        rows = cursor.fetchall()
        courses = [{'class_code': row[0], 'subject': row[1]} for row in rows]
        return jsonify({'courses': courses, 'userType': user_type})

    except Error as e:
        print("Error while connecting to MySQL", e)
        return jsonify({'error': str(e)}), 500
    finally:
        if conn and conn.is_connected():
            cursor.close()
            conn.close()
@app.route('/get-earliest-year')
def get_earliest_year():
    conn = None
    try:
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT MIN(Year) FROM Class")  # 替换为您的实际查询
        earliestYear = cursor.fetchone()[0]
        return jsonify({'earliestYear': earliestYear})
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()
@app.route('/search/<user_id>', methods=['POST'])
def search(user_id):
    data = request.json
    year = data.get('year')
    semester = data.get('semester')
    subject = data.get('subject')
    user_type = get_user_type(user_id)
    try:
        conn = create_connection()
        with conn.cursor() as cursor:
            if user_type == 'Student':
                query = """
                    SELECT
                        si.Student_ID, si.Student_Name, si.Major,
                        cl.Year, cl.Semester, cl.Subject, gr.Score, pi.Professor_Name,cl.Class_code
                    FROM
                        Grade gr
                    JOIN
                        Class cl ON gr.Class_code = cl.Class_code
                    JOIN
                        Student_Info si ON gr.Student_ID = si.Student_ID
                    JOIN
                        Professor_Info pi ON cl.Professor_ID = pi.Professor_ID
                    WHERE
                        si.Student_ID = %s
                """
                params = [user_id]
            elif user_type == 'Professor':
                query = """
                    SELECT
                        si.Student_ID, si.Student_Name, si.Major,
                        cl.Year, cl.Semester, cl.Subject, gr.Score, cl.Professor_ID,cl.Class_code
                    FROM
                        Grade gr
                    JOIN
                        Class cl ON gr.Class_code = cl.Class_code
                    JOIN
                        Student_Info si ON gr.Student_ID = si.Student_ID
                    WHERE
                        cl.Professor_ID = %s
                """    
                params = [user_id]
            elif user_type == 'TA':
                query = """
                    SELECT
                        si.Student_ID, si.Student_Name, si.Major,
                        cl.Year, cl.Semester, cl.Subject, gr.Score, pi.Professor_Name,cl.Class_code
                    FROM
                        Grade gr
                    JOIN
                        Class cl ON gr.Class_code = cl.Class_code
                    JOIN
                        Student_Info si ON gr.Student_ID = si.Student_ID
                    JOIN
                        Professor_Info pi ON cl.Professor_ID = pi.Professor_ID
                    WHERE
                        si.Student_ID = %s OR cl.TA_ID= %s
                """
                params = [user_id,user_id]
            else:
                # 如果用户既不是教授也不是TA，则返回错误或空数据
                return jsonify({'error': 'Unauthorized access'}), 403
            if year:
                query += " AND cl.Year = %s"
                params.append(year)
            if semester:
                query += " AND cl.Semester = %s"
                params.append(semester)
            if subject:
                query += " AND cl.Class_code = %s"
                params.append(subject)

            cursor.execute(query, params)
            results = cursor.fetchall()

            data = [{
                'Student ID': row[0],
                'Name': row[1],
                'Major': row[2],
                'Year': row[3],
                'Semester': row[4],
                'Subject': row[5],
                'Score': row[6],
                'Class_code': row[8]
            } for row in results]
            return jsonify(data)

    except Error as e:
        return jsonify({'error': str(e)}), 501
    finally:
        if conn:
            conn.close()

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/upload/preview', methods=['POST'])
def upload_preview():
    if 'file' not in request.files:
        return jsonify({"message": "No file found"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"message": "No selected file"}), 400

    # 检查 MIME 类型
    if file.content_type not in ALLOWED_MIME_TYPES:
        return jsonify({"message": "Unsupported file type"}), 400

    # 保存文件
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    # 检查文件内容
    try:
        if filename.endswith('.csv'):
            df = pd.read_csv(filepath)
        elif filename.endswith('.xlsx'):
            df = pd.read_excel(filepath, engine='openpyxl')
        elif filename.endswith('.xls'):
            df = pd.read_excel(filepath, engine='xlrd')
        else:
            return jsonify({"message": "Unsupported file extension"}), 400

        if not EXPECTED_COLUMNS.issubset(df.columns):
            return jsonify({"message": "Document's content doesn't match."}), 400
        df = enrich_data(df)
        # 将 DataFrame 转换为 JSON 格式以供前端预览
        preview_data = df.to_json(orient='records')
        return jsonify({"preview": preview_data})
    except Exception as e:
        print(f"Error processing file: {e}")
        return jsonify({"message": "Error processing file"}), 500

def enrich_data(df):
    conn = create_connection()  # 创建数据库连接
    try:
        for index, row in df.iterrows():
            student_id = row['Student_ID']
            class_code = row['Class_code']

            # 从数据库获取额外信息
            additional_info = get_additional_info(conn, student_id, class_code)
            print(f"Additional info for {student_id}, {class_code}: {additional_info}")
            # 将额外信息添加到 DataFrame
            
            for key, value in additional_info.items():
                df.at[index, key] = value
        df.rename(columns={'Student_ID': 'Student ID'}, inplace=True)
    finally:
        conn.close()
    print("Enriched DataFrame:\n", df.head())  
    return df

def get_additional_info(conn, student_id, class_code):
    # 这里编写SQL查询以获取额外信息
    cursor = conn.cursor()
    query = """SELECT si.Student_Name, si.Major, cl.Year, cl.Semester, cl.Subject
               FROM Student_Info si, Class cl
               WHERE si.Student_ID = %s AND cl.Class_code = %s"""
    cursor.execute(query, (student_id, class_code))
    result = cursor.fetchone()
    if result:
        return {
            'Name': result[0],'Major': result[1],'Year': result[2],'Semester': result[3],'Subject': result[4]
        }
    return {}

@app.route('/save/grades', methods=['POST'])
def save_grades():
    grades = request.json.get('grades', [])
    conn = create_connection()
    try:
        with conn.cursor() as cursor:
            for item in grades:
                student_id = item['Student ID']
                class_code = item['Class_code']
                score = item['Score']
                if student_id and class_code and score is not None:
                    update_query = """UPDATE Grade SET Score = %s WHERE Student_ID = %s AND Class_code = %s"""
                    cursor.execute(update_query, (score, student_id, class_code))
        conn.commit()
        return jsonify({"message": "Grades updated successfully"})
    except Error as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/export', methods=['POST'])
def export_data():
    data = request.json.get('data', [])  # 从请求中获取数据
    if not data:
        return jsonify({"message": "No data to export"}), 400
    # 将数据转换为 DataFrame
    df = pd.DataFrame(data)
    # 将 DataFrame 转换为 Excel 文件
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    return send_file(
    output,
    mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    as_attachment=True,
    download_name="exported_data.xlsx")
if __name__ == '__main__':
    app.run(debug=True)