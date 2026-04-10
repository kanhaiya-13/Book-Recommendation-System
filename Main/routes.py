from flask import Flask, render_template, url_for, flash, redirect, request
from Main.form import RegistrationForm, LoginForm, BookForm, UploadBook, Contact, DeleteBook, UpdateAccount
from Main.recomm import recom, bookdisp
from Main.models import User
from flask_sqlalchemy import SQLAlchemy
from Main import app,db,bcrypt
from flask_mail import Message
import secrets
import os
from PIL import Image
import pandas as pd
import boto3
import io
import numpy as np
from flask_login import login_user, current_user, logout_user, login_required
import csv
from csv import writer

posts = [
	{
	'author' : 'Eshita Jain',
	'title' : 'International Institute of Information Technology'
	}
]

@app.route("/")
@app.route("/home")
def home():
	list1=bookdisp()
	return render_template('home.html',content=list1)



@app.route("/about")
def about():
	return render_template('about.html',posts=posts,title="About")



@app.route("/register", methods=['GET','POST'])
def register():
	if current_user.is_authenticated:
		return redirect(url_for('home'))
	form = RegistrationForm()
	if form.validate_on_submit():
		hashed_password=bcrypt.generate_password_hash(form.password.data).decode('utf-8')
		user=User(username=form.username.data,email=form.email.data,password=hashed_password)
		db.session.add(user)
		db.session.commit()
		flash(f'Account Created for { form.username.data } !', 'success')
		return redirect(url_for('login'))
	return render_template('register.html',title='Register',form=form)


@app.route("/login", methods=['GET','POST'])
def login():
	if current_user.is_authenticated:
		return redirect(url_for('home'))
	form = LoginForm()
	if form.validate_on_submit():
		user=User.query.filter_by(email=form.email.data).first()
		if user and bcrypt.check_password_hash(user.password, form.password.data):
			login_user(user, remember=form.remember.data)
			next_page=request.args.get('next')
			flash(f'User Login Successful !','success')
			return redirect(next_page) if next_page else redirect(url_for('account'))
		else:
			flash(f'Login Unsuccessful. Please check email and password.', 'danger')
	return render_template('login.html',title='Login',form=form)


@app.route("/recommender",methods=['GET','POST'])
def recommender():
	form=BookForm()
	df=pd.read_csv("Bookz.csv")
	if form.validate_on_submit():
		book=form.bookname.data
		final_list = recom(book)
		if final_list:
			flash(f'Here are the following recommendations for you', 'success')
		else:
			flash(f'Book "{book}" not found in our database. Please try a different book title.', 'warning')
		return render_template('recommender.html',title='Recommender',form=form,final=final_list)
	return render_template('recommender.html',title='Recommender',form=form)

def upload(file_name, list_of_elem):
    with open(file_name, 'a+', newline='') as write_obj:
        csv_writer = writer(write_obj)
        csv_writer.writerow(list_of_elem)


@app.route("/uploadbook",methods=['GET','POST'])
@login_required
def uploadbook():
	form=UploadBook()
	df=pd.read_csv('Bookz.csv')
	if form.validate_on_submit():
		i=max(df['index']+1)
		li=[i,i,form.ISBN.data,form.Title.data,form.Author.data,form.Publisher.data]
		upload('Book.csv',li)
		flash(f'Book Uploaded Succesfully', 'success')
		return redirect(url_for('home'))
	return render_template('uploadbook.html',title='Upload Book',form=form)


@app.route("/contact",methods=['GET','POST'])
@login_required
def contact():
	form=Contact()
	cur=current_user.username
	return render_template('contact.html',title='Contact',current=cur,form=form)

def delete(isbn_num,file_name):
	lines=list()
	with open(file_name, 'r') as readFile:
	    reader = csv.reader(readFile)
	    for row in reader:
	        lines.append(row)
	        for field in row:
	            if field == isbn_num:
	                lines.remove(row)
	with open(file_name, 'w') as writeFile:
	    writer = csv.writer(writeFile)
	    writer.writerows(lines)


@app.route("/deletebook",methods=['GET','POST'])
@login_required
def deletebook():
	form=DeleteBook()
	if form.validate_on_submit():
		delete(form.ISBN.data,'Bookz.csv')
		flash(f'Book is Deleted', 'success')
		return redirect(url_for('home'))
	return render_template('deletebook.html',title='Delete Book',form=form)


@app.route("/logout")
def logout():
	logout_user()
	flash(f'You have been logged out successfully !','success')
	return redirect(url_for('home'))


def save_picture(form_picture):
	random_hex=secrets.token_hex(8)
	f_name, f_ext = os.path.splitext(form_picture.filename)
	picture_fn = random_hex + f_ext

	# Resize image
	op_size=(125,125)
	i=Image.open(form_picture)
	i.thumbnail(op_size)
	
	# Save to in-memory bytes
	in_mem_file = io.BytesIO()
	# Ensure RGBA is converted to RGB for JPEG format saving
	if i.mode == 'RGBA' and f_ext.lower() in ['.jpg', '.jpeg']:
		i = i.convert('RGB')
	i.save(in_mem_file, format=i.format if i.format else 'JPEG')
	in_mem_file.seek(0)
	
	s3_client = boto3.client(
		's3',
		aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
		aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
		region_name=os.environ.get('S3_REGION_NAME', 'us-east-1')
	)
	s3_bucket = os.environ.get('S3_BUCKET_NAME', 'my-book-recommendation-images')
	
	s3_client.upload_fileobj(
		in_mem_file,
		s3_bucket,
		picture_fn,
		ExtraArgs={'ContentType': form_picture.content_type}
	)

	return picture_fn

@app.route("/account",methods=['GET','POST'])
@login_required
def account():
	form = UpdateAccount()
	if form.validate_on_submit():
		if form.picture.data:
			pic_file=save_picture(form.picture.data)
			current_user.image_file=pic_file
		current_user.username=form.username.data
		current_user.email=form.email.data
		db.session.commit()
		flash('Your account has been updated','success')
		return redirect(url_for('account'))
	elif request.method == 'GET':
		form.username.data=current_user.username
		form.email.data=current_user.email
		
	if current_user.image_file == 'default.jpg':
		image_file=url_for('static', filename='profile_pics/'+current_user.image_file)
	else:
		s3_bucket = os.environ.get('S3_BUCKET_NAME', 'my-book-recommendation-images')
		s3_region = os.environ.get('S3_REGION_NAME', 'us-east-1')
		image_file = f"https://{s3_bucket}.s3.{s3_region}.amazonaws.com/{current_user.image_file}"
		
	return render_template('account.html', title='Account',image_file=image_file, form = form)