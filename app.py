from flask import Flask, render_template, request, redirect, url_for, session, flash
from supabase import create_client
import datetime
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Set a secure secret key for session management

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Auth middleware
def auth_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        try:
            # Register the user with Supabase Auth
            response = supabase.auth.sign_up({
                "email": email,
                "password": password,
            })
            
            if response.user:
                flash('Registration successful! Please check your email to confirm your account.', 'success')
                return redirect(url_for('login'))
            else:
                flash('Registration failed. Please try again.', 'error')
        except Exception as e:
            flash(f'An error occurred: {str(e)}', 'error')
    
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        try:
            # Sign in the user with Supabase Auth
            response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if response.user:
                # Store user information in session
                session['user_id'] = response.user.id
                session['user_email'] = response.user.email
                session['access_token'] = response.session.access_token
                
                # Redirect to dashboard or home
                next_page = request.args.get('next')
                return redirect(next_page or url_for('index'))
            else:
                flash('Login failed. Please check your credentials.', 'error')
        except Exception as e:
            flash(f'An error occurred: {str(e)}', 'error')
    
    return render_template('login.html')


    
    
@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        email = request.form.get('email')
        try:
            # Trigger password reset with Supabase Auth (correct method)
            response = supabase.auth.reset_password_for_email(email)
            
            if response.get('error') is None:
                flash('Password reset instructions have been sent to your email.', 'success')
                return redirect(url_for('login'))
            else:
                flash('Failed to send reset instructions. Please check the email provided.', 'error')
        except Exception as e:
            flash(f'An error occurred: {str(e)}', 'error')
    
    return render_template('reset_password.html')



@app.route('/logout')
def logout():
    # Clear the session
    session.clear()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('login'))

@app.route('/')
@auth_required
def index():
    # Fetch ingredients from Supabase
    response = supabase.table('ingredients').select('*').eq('user_id', session['user_id']).execute()
    ingredients = response.data if response.data else []
    
    # Fetch recipes from Supabase
    response = supabase.table('recipes').select('*').execute()
    recipes = response.data if response.data else []
    
    # Highlight ingredients that expire soon (3 days or less)
    today = datetime.date.today()
    for ingredient in ingredients:
        expiration_date = datetime.datetime.strptime(ingredient['expiration_date'], "%Y-%m-%d").date()
        ingredient['expires_soon'] = (expiration_date - today).days <= 3
    
    # Count how many expiring ingredients are in each recipe
    for recipe in recipes:
        expiring_count = 0
        recipe_ingredients = recipe['ingredients'].split(",")  # Assuming ingredients are stored as comma-separated strings
        for ingredient_name in recipe_ingredients:
            ingredient_name = ingredient_name.strip()
            for ingredient in ingredients:
                if ingredient_name == ingredient['name']:
                    expiration_date = datetime.datetime.strptime(ingredient['expiration_date'], "%Y-%m-%d").date()
                    if (expiration_date - today).days <= 3:
                        expiring_count += 1
        recipe['expiring_count'] = expiring_count
    
    # Sort recipes based on expiring_count (most expiring ingredients first)
    recipes.sort(key=lambda recipe: recipe['expiring_count'], reverse=True)
    
    # Render the HTML with ingredients and recipes
    return render_template('index.html', ingredients=ingredients, recipes=recipes, user_email=session.get('user_email'))

@app.route('/add', methods=['POST'])
@auth_required
def add_ingredient():
    name = request.form.get('name')
    expiration_date = request.form.get('expiration_date')
    
    if name and expiration_date:
        supabase.table('ingredients').insert({
            'name': name,
            'expiration_date': expiration_date,
            'user_id': session['user_id']  # Associate ingredient with user
        }).execute()
    
    return redirect(url_for('index'))

@app.route('/delete/<int:ingredient_id>')
@auth_required
def delete_ingredient(ingredient_id):
    # Make sure this ingredient belongs to the current user
    supabase.table('ingredients').delete().eq('id', ingredient_id).eq('user_id', session['user_id']).execute()
    return redirect(url_for('index'))

@app.route('/edit/<int:ingredient_id>', methods=['POST'])
@auth_required
def edit_ingredient(ingredient_id):
    name = request.form.get('name')
    expiration_date = request.form.get('expiration_date')
    
    if name and expiration_date:
        # Make sure this ingredient belongs to the current user
        supabase.table('ingredients').update({
            'name': name,
            'expiration_date': expiration_date
        }).eq('id', ingredient_id).eq('user_id', session['user_id']).execute()
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
