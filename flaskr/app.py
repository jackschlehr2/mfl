from flask import Flask, render_template, request, json, session, redirect, url_for, abort
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import requests
from datetime import date
mysql = MySQL()

app = Flask(__name__)
 
# MySQL configurations
app.config['MYSQL_USER'] = 'jschlehr'
app.config['MYSQL_PASSWORD'] = 'notr3dam3'
app.config['MYSQL_DB'] = 'jschlehr'
app.config['MYSQL_HOST'] = 'localhost'
app.secret_key = "supersecretkey321"
mysql.init_app(app)


def login_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            return redirect(url_for( 'login') )

    return wrap


@app.route("/")
def main():
    teams = get_teams()

    return render_template('index.html', teams=teams)

 
@app.route("/team-rankings")
def rankings():
    teams = get_teams()
    return render_template( 'rankings.html', teams=teams )

@app.route("/team/<team_name>")
def team_profile(team_name):
    team = team_name
    return render_template( 'team.html', team=team)

@app.route("/feed")
@login_required
def feed():
    games = get_games()
    bets = get_bets()
    comments = get_comments()
    return render_template( 'feed.html', bets=bets, comments=comments, games=games)



@app.route('/sign-up', methods=['POST','GET'])
def signUp():
    if request.method == 'GET':
        return render_template('signup.html')
    else:
        _name = request.form['inputName']
        _email = request.form['inputEmail']
        _password = request.form['inputPassword1']
        _password2 = request.form['inputPassword2']
        if _password and (_password != _password2 ):
            return render_template('signup.html', message={"status":"message"
                ,"message":"passwords don't match" })
        if _name and _email and _password:
            if username_exists(_name):
                return render_template('signup.html', message={"status":"message"
                ,"message":"username exists" })
            conn = mysql.connection
            curr = conn.cursor()
            _hashed_password = generate_password_hash(_password)
            curr.execute("INSERT INTO users (user_username, user_password, user_email) VALUES (%s, %s, %s)", 
                                                    ( _name, _hashed_password, _email ) )
            conn.commit()
            session['logged_in'] = True
            session['user_name'] = _name
            curr.execute( "SELECT * FROM users WHERE user_id = @@Identity" )
            data = curr.fetchall()
            session['user_id'] = data[0][0]
            return render_template('account.html',account_name=session['user_name'],  message={"status":"success", "message":"Account Successfully made!"} )
        else:
            return render_template('signup.html', message={"status":"error", "message":"an error was encountered, try again"} )

def username_exists(username):
    conn = mysql.connection
    curr = conn.cursor()
    #query= "SELECT * FROM users WHERE user_username = \"{user}\"".format(user=username)
    curr.execute("SELECT * FROM users WHERE user_username = %(username)s", {'username': username}) #injection protected
    data = curr.fetchall()
    if len(data) > 0:
        return True
    return False


@app.route( "/profile/<username>", methods=['POST','GET'])
@login_required
def view_profile(username):
    conn = mysql.connection
    curr = conn.cursor()
    wins=10
    curr.execute("SELECT * FROM users WHERE user_username = %(username)s", {'username': username}) #injection protected
    data = curr.fetchall()
    num_followers=0
    num_following=0
    return render_template('profile.html')


    



@app.route('/login', methods=['POST', 'GET'] )
def login():
    if request.method=='GET':
        return render_template('login.html')
    elif request.method=='POST':
        _username = request.form['inputName']
        _password = request.form['inputPassword']
        if not (_username and _password):
            return render_template( 'index.html', message={"status":"error", "message":"error occured"})
        if _username and _password:
            conn = mysql.connection
            curr = conn.cursor()
            curr.execute("SELECT * FROM users WHERE user_username = (%s) or user_email = (%s)", ( _username, _username ))
            
            data = curr.fetchall()
            if not data:
                return render_template('login.html', message={"status":"error", "message":"Incorrect username or password"})
            # TODO: case where query returns more than one result
            # refactor to make more robust
            query_password = data[0][1]
            print(data)
            print( query_password )
            # TODO fix so that the returns are better
            
            if check_password_hash(query_password, _password):
                session['logged_in'] = True
                session['user_id'] = data[0][0]
                session['user_name'] = _username
                return render_template('account.html', message={"status":"success", "message":"Logged In!"} )
            return render_template('login.html', message={"status":"error", "message":"Incorrect username or password"})




@app.route( '/account', methods=['GET'])
@login_required
def account():
    uname = session['user_name']
    return render_template('account.html', account_name=session['user_name'], friends=get_friends(uname), wins=get_wins(uname))

@app.route( '/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method=='GET':
        return render_template('change_password.html')
    elif request.method=='POST':
        old_password_from_form = request.form['oldPassword']
        new_password1 = request.form['newPassword1']
        new_password2 = request.form['newPassword2']
        if new_password1 != new_password2: 
            return render_template('change_password.html', message="Passwords Not Same")

        conn = mysql.connection
        curr = conn.cursor()
        _user_id = session['user_id']
        #query = "SELECT user_password FROM users WHERE user_id = {user_id}".format(user_id=_user_id )
        curr.execute("SELECT user_password FROM users WHERE user_id = %(_user_id)s", {'_user_id': _user_id}) #injection protected
        data = curr.fetchall()
        current_password = data[0][0]
        if check_password_hash(current_password, old_password_from_form ):
            new_password_hash = generate_password_hash(new_password2)
            query = "UPDATE users SET user_password = \"{new_password_hash}\" where user_id = {user_id}".format(new_password_hash=new_password_hash, user_id=_user_id )
            conn = mysql.connection
            curr = conn.cursor()
            curr.execute("UPDATE users SET user_password = %s where user_id = %s", (new_password_hash, _user_id))
            #curr.execute(query)
            conn.commit()
            return render_template('account.html', message="Password Updated", wins=get_wins(session['user_name']))
        else:
            return render_template('change_password.html', message="Password Not Correct")
    else:
        return {'status':'error'}


@app.route( '/delete-account', methods=['GET', 'POST'])
@login_required
def delete_account():
    if request.method=='GET':
        return render_template('delete_account.html')
    elif request.method=='POST':
        new_password1 = request.form['newPassword1']
        new_password2 = request.form['newPassword2']
        if new_password1 != new_password2: 
            return render_template('delete_account.html', message="Passwords Not Same")

        conn = mysql.connection
        curr = conn.cursor()
        _user_id = session['user_id']
        query = "SELECT user_password FROM users WHERE user_id = {user_id}".format(user_id=_user_id )
        curr.execute("SELECT user_password FROM users WHERE user_id = %(_user_id)s", {'_user_id': _user_id}) #injection protected
        data = curr.fetchall()
        current_password = data[0][0]
        if check_password_hash(current_password, new_password2 ):
            #delete_query = "DELETE from users where user_id = {user_id}".format(user_id=_user_id )
            conn = mysql.connection
            curr = conn.cursor()
            curr.execute("DELETE from users where user_id = %(_user_id)s", {'_user_id': _user_id}) #injection protected
            conn.commit()
            session['logged_in'] = False
            return redirect( "/" )
        else:
            return render_template('delete_account.html', message="Password Not Correct")
    else:
        return {'status':'error'}


def get_users():
    conn = mysql.connection
    curr = conn.cursor()
    curr.execute("SELECT user_username FROM users" )
    data = curr.fetchall()
    return data

# trying to make join to get if already friends or not
# SELECT user_username, user_id 
# FROM users 
# full outer join friends on users.user_id = friends.friend_id 
# where  friends.user_id=(%s), 

def get_bets():
    conn = mysql.connection
    curr = conn.cursor()
    curr.execute("select bets.*, case when likes.likes is NULL THEN 0 ELSE likes.likes END AS likes from (select bet_id, count(*) as likes from likes group by bet_id) likes right outer join bets on likes.bet_id=bets.bet_id order by submitted_date desc" )
    data = curr.fetchall()
    data = list(data)
    for index, bet in enumerate( data ):
        game_id = str(bet[8])
        query = "Select home_team, away_team FROM games where id= {game_id}".format(game_id=game_id)
        curr.execute( query )
        teams = curr.fetchall()
        data[index] = list(data[index]) + list(teams[0])
        winner_id = str(bet[7])
        query = "Select team_name FROM teams where team_id= {winner_id}".format(winner_id=winner_id)
        curr.execute( query )
        teams = curr.fetchall()
        print(teams)
        data[index] = list(data[index]) + list(teams[0])
        print(data[index])
    return data



def get_comments():
    conn = mysql.connection
    curr = conn.cursor()
    curr.execute("SELECT comments.user_id, comments.bet_id, comments.comment, users.user_username FROM comments, users WHERE comments.user_id=users.user_id")
    data = curr.fetchall()
    data = list(data)
    return data



def get_teams():
    conn = mysql.connection
    curr = conn.cursor()
    curr.execute( "Select team_name, wins, losses, PF, PA from teams order by wins DESC, PF DESC" )
    data = curr.fetchall()
    return data


def update_standings():
    conn = mysql.connection
    curr = conn.cursor()
    curr.execute( "update teams, \
     ( select count( loser_id ) as losses, loser_id  from ( Select home_score, away_score, home_team_id,away_team_id, \ if(  home_score<away_score, home_team_id, away_team_id ) as loser_id from games where home_score != 0 or \
     away_score != 0 ) loss group by loser_id ) lossers \
    set teams.losses=lossers.losses \
    where teams.team_id=lossers.loser_id" )


    '''
    ---------------QUERY to update the number of losses ---------------------------------------------------------
    update teams, 
     ( select count( loser_id ) as losses, loser_id  from ( Select home_score, away_score, home_team_id,  away_team_id, if(  home_score<away_score, home_team_id, away_team_id ) as loser_id from games where home_score != 0 or away_score != 0 ) loss group by loser_id ) lossers
    set teams.losses=lossers.losses
    where teams.team_id=lossers.loser_id


    ---------------query to update the number of wins---------------------------------------------------------
    update teams,
    ( select count( winner_id ) as wins, winner_id  from ( Select home_score, away_score, home_team_id,  away_team_id, if(  home_score>away_score, home_team_id, away_team_id ) as winner_id from games where home_score != 0 or away_score != 0 ) win group by winner_id ) winners
    set teams.wins=winners.wins
    where teams.team_id=winners.winner_id

    -------------------Query to update PF--------------------------------------------------------------
    update teams, 
    ( select sum(PF) as PF, team_id from 
    ( select sum( away_score ) as PF, away_team_id as team_id from games group by away_team_id 
    union
    select sum( home_score ) as PF, home_team_id as team_id from games group by home_team_id ) h
    group by  team_id ) PF
    set teams.PF=PF.PF
    where teams.team_id=PF.team_id


    
    

    

    -------------------Query to update PA--------------------------------------------------------------

    update teams,
    ( select sum(PA) as PA, team_id from 
    ( select sum( away_score ) as PA, home_team_id as team_id from games group by home_team_id 
    union
    select sum( home_score ) as PA, away_team_id as team_id from games group by away_team_id ) h
    group by  team_id ) PA
    set teams.PA=PA.PA
    where teams.team_id=PA.team_id


    '''

    
    

    


def get_num_followers( username ):
    conn = mysql.connection
    curr = conn.cursor()
    curr.execute( )



@app.route( '/new-bet', methods=[ 'POST'])
@login_required
def bet():
    
    bet_amount = int( request.form['betAmount'] )
    game_id = request.form['moneyline'].split(",")
    print(game_id)

    home_away = game_id[0]
    print(game_id[1].strip())
    winner_id = int(game_id[2].strip())

    game_id = int(game_id[1].strip())
    print(game_id)



    if bet_amount and home_away and game_id:
        conn = mysql.connection
        curr = conn.cursor()
        query = "INSERT INTO bets (amount, submitted_date, user_id, type, game_id, user_username,winner_id) \
                        VALUES  ({bet_amount}, NOW(), {user_id}, \"{type2}\", \"{game_id}\",  \"{user_username}\", {winner_id})".format( bet_amount=bet_amount, user_id=int(session['user_id']), game_id=game_id, type2=home_away, user_username=session["user_name"], winner_id=winner_id )

        curr.execute( query )
        conn.commit()
        
    else:
        return {'status':'fail'}
    return redirect( "feed" )


@app.route("/scores")
def scores():
    conn = mysql.connection
    curr = conn.cursor()
    query = "SELECT  home_team, away_team, DATE_FORMAT(date,'%m-%d'), home_score, away_score FROM games order by date"
    curr.execute(query)
    games = curr.fetchall()
    print(games)
    return render_template( 'scores.html', games=games)

def get_games():
    conn = mysql.connection
    curr = conn.cursor()
    query = "SELECT  home_team, away_team, DATE_FORMAT(date,'%m-%d'), home_team_moneyline, away_team_moneyline, id, home_team_id, away_team_id FROM games where date > CURDATE() order by date  limit 10"
    curr.execute(query)
    data = curr.fetchall()
    if not data:
        abort(500)
    return data
   

@app.route( '/like/<bet_id>', methods=['POST'])
@login_required
def like(bet_id):
    # check if already liked
    conn = mysql.connection
    curr = conn.cursor()
    # check if already like or the user it is the user's own post
    curr.execute("select bet_id, user_id from likes where bet_id=%s and user_id=%s \
                  UNION  \
                  select bet_id, user_id from bets  where bet_id=%s and user_id=%s " \
                ,(bet_id, session['user_id'], bet_id, session['user_id'],) )
    data = curr.fetchall()
    if len(data) > 0: 
        abort(405)
    
    try:
        conn = mysql.connection
        curr = conn.cursor()
        user_id=session['user_id']
        curr.execute("Insert ignore into likes VALUES(%s,%s)", (user_id, bet_id,  ) )
        conn.commit()
        
        return {'status':'success'}
    except Exception as e:
        print(e) 
        return {'status':'error'}

@app.route('/comment/<bet_id>')
@login_required
def comment(bet_id):
    return render_template('comment.html', selected='comment', bet_id=bet_id)
        
@app.route('/comment2/<bet_id>', methods = ['POST'])
@login_required
def comment2(bet_id):
    comment=request.form['comment']
    try:
        conn = mysql.connection
        curr = conn.cursor()
        user_id=session['user_id']
        curr.execute("Insert ignore into comments VALUES(%s,%s,%s)", (user_id, bet_id, comment))
        conn.commit()
        bets = get_bets()
        comments = get_comments()
        return render_template( 'feed.html', bets=bets, comments=comments)
    except Exception as e:
        print(e) 
        return {'status':'error'}


@app.route( '/logout', methods=['GET'])
@login_required
def logout():
    session.clear()
    return redirect( url_for( "main", message={"status":"nothing", "message":"Logged Out"} ) )


if __name__== "__main__":
    app.run(port=8000, host="0.0.0.0")



