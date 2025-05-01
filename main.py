from flask import Flask, request, jsonify
from flask_cors import CORS
from flask import send_from_directory
import boto3
import os
import uuid
from datetime import datetime
import json
from decimal import Decimal
from dotenv import load_dotenv
from boto3.dynamodb.conditions import Key, Attr

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": ["https://yourfrontenddomain.com"]}})

# Helper class for DynamoDB JSON serialization
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super(DecimalEncoder, self).default(o)

# Initialize DynamoDB client
dynamodb = boto3.resource(
    'dynamodb',
    region_name=os.getenv('AWS_REGION', 'us-east-1'),
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),  # From .env
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
)

# Define table references
blog_table = dynamodb.Table(os.getenv('BLOG_TABLE_NAME', 'blog_posts'))
featured_table = dynamodb.Table(os.getenv('FEATURED_TABLE_NAME', 'featured_posts'))
contact_table = dynamodb.Table(os.getenv('CONTACT_TABLE_NAME', 'contact_submissions'))
donation_table = dynamodb.Table(os.getenv('DONATION_TABLE_NAME', 'donation_info'))
volunteer_table = dynamodb.Table(os.getenv('VOLUNTEER_TABLE_NAME', 'volunteer_applications'))
partner_table = dynamodb.Table(os.getenv('PARTNER_TABLE_NAME', 'partnership_requests'))

# Configure Flask to use custom JSON encoder for Decimal objects
app.json_encoder = DecimalEncoder

# Blog endpoints
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(
         os.path.join(app.root_path, 'static'),  # Folder with favicon.ico
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon'
    )
def home():
    return jsonify({
        'message': 'Welcome to Radiant Hope Media API',
        'status': 'running',
        'timestamp': datetime.now().isoformat()
    })
@app.route('/api/blog', methods=['GET'])
def get_blog_posts():
    """
    Get blog posts with pagination
    Query parameters:
    - page: page number (default: 1)
    - per_page: items per page (default: 3)
    """
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 3))
    
    # Calculate start and end indices for pagination
    start = (page - 1) * per_page
    
    # Scan DynamoDB table
    try:
        response = blog_table.scan()
        items = response.get('Items', [])
        
        # Sort by date (newest first)
        items.sort(key=lambda x: x.get('date', ''), reverse=True)
        
        # Paginate results
        paginated_items = items[start:start + per_page]
        total_items = len(items)
        total_pages = (total_items + per_page - 1) // per_page
        
        return jsonify({
            'posts': paginated_items,
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages,
            'total_items': total_items
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/blog/featured', methods=['GET'])
def get_featured_posts():
    """Get featured blog posts"""
    try:
        response = featured_table.scan()
        items = response.get('Items', [])
        return jsonify({'featured_posts': items})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/blog/<post_id>', methods=['GET'])
def get_blog_post(post_id):
    """Get a specific blog post by ID"""
    try:
        response = blog_table.get_item(Key={'id': post_id})
        item = response.get('Item')
        if not item:
            return jsonify({'error': 'Post not found'}), 404
        return jsonify(item)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/blog', methods=['POST'])
def create_blog_post():
    """Create a new blog post (admin only)"""
    try:
        data = request.json
        post_id = str(uuid.uuid4())
        current_date = datetime.now().strftime('%b %d, %Y')
        
        new_post = {
            'id': post_id,
            'title': data.get('title'),
            'date': data.get('date', current_date),
            'img': data.get('img'),
            'tag': data.get('tag'),
            'content': data.get('content'),
            'author': data.get('author', 'Anonymous'),
            'read_time': data.get('read_time', '3 min'),
            'likes': data.get('likes', 0),
            'comments_count': data.get('comments_count', 0)
        }
        
        blog_table.put_item(Item=new_post)
        return jsonify({'message': 'Post created successfully', 'post_id': post_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/blog/<post_id>', methods=['PUT'])
def update_blog_post(post_id):
    """Update an existing blog post"""
    try:
        data = request.json
        
        # Check if post exists
        response = blog_table.get_item(Key={'id': post_id})
        if 'Item' not in response:
            return jsonify({'error': 'Post not found'}), 404
            
        update_expression_parts = []
        expression_attribute_values = {}
        
        # Build update expression dynamically based on provided fields
        if 'title' in data:
            update_expression_parts.append('title = :title')
            expression_attribute_values[':title'] = data['title']
            
        if 'img' in data:
            update_expression_parts.append('img = :img')
            expression_attribute_values[':img'] = data['img']
            
        if 'tag' in data:
            update_expression_parts.append('tag = :tag')
            expression_attribute_values[':tag'] = data['tag']
            
        if 'content' in data:
            update_expression_parts.append('content = :content')
            expression_attribute_values[':content'] = data['content']
            
        if 'author' in data:
            update_expression_parts.append('author = :author')
            expression_attribute_values[':author'] = data['author']
            
        if 'read_time' in data:
            update_expression_parts.append('read_time = :read_time')
            expression_attribute_values[':read_time'] = data['read_time']
            
        if 'likes' in data:
            update_expression_parts.append('likes = :likes')
            expression_attribute_values[':likes'] = data['likes']
            
        if 'comments_count' in data:
            update_expression_parts.append('comments_count = :comments_count')
            expression_attribute_values[':comments_count'] = data['comments_count']
            
        # If no fields to update, return error
        if not update_expression_parts:
            return jsonify({'error': 'No fields to update'}), 400
            
        # Construct the update expression
        update_expression = 'SET ' + ', '.join(update_expression_parts)
        
        # Update the item
        response = blog_table.update_item(
            Key={'id': post_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values,
            ReturnValues='UPDATED_NEW'
        )
        
        return jsonify({
            'message': 'Post updated successfully',
            'updated_attributes': response.get('Attributes', {})
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/blog/<post_id>', methods=['DELETE'])
def delete_blog_post(post_id):
    """Delete a blog post by ID"""
    try:
        # Check if post exists
        response = blog_table.get_item(Key={'id': post_id})
        if 'Item' not in response:
            return jsonify({'error': 'Post not found'}), 404
            
        # Delete the item
        blog_table.delete_item(Key={'id': post_id})
        
        return jsonify({'message': 'Post deleted successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Contact form endpoints
@app.route('/api/contact', methods=['POST'])
def submit_contact_form():
    data = request.json
    if not all(key in data for key in ['name', 'email', 'message']):
        return jsonify({'error': 'Missing required fields'}), 400
    try:
        data = request.json
        submission_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        submission = {
            'id': submission_id,
            'name': data.get('name'),
            'email': data.get('email'),
            'subject': data.get('subject'),
            'message': data.get('message'),
            'submitted_at': timestamp
        }
        
        contact_table.put_item(Item=submission)
        return jsonify({'message': 'Contact form submitted successfully', 'submission_id': submission_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/contact', methods=['GET'])
def get_contact_submissions():
    """Get all contact form submissions"""
    try:
        response = contact_table.scan()
        items = response.get('Items', [])
        
        # Sort by submission time (newest first)
        items.sort(key=lambda x: x.get('submitted_at', ''), reverse=True)
        
        return jsonify({'submissions': items})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Get Involved endpoints
@app.route('/api/involved/donation', methods=['GET'])
def get_donation_info():
    """Get donation account details"""
    try:
        response = donation_table.scan(Limit=1)
        items = response.get('Items', [])
        if not items:
            # Return default info if none exists in the database
            return jsonify({
                'account_number': '8281412432',
                'bank_name': 'Moniepoint MFB',
                'account_name': 'Radiant Hope Media'
            })
        return jsonify(items[0])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/involved/donation', methods=['POST'])
def update_donation_info():
    """Update donation account details"""
    try:
        data = request.json
        
        # Use a fixed ID for the donation info (there should be only one record)
        donation_id = 'donation-info-001'
        
        donation_info = {
            'id': donation_id,
            'account_number': data.get('account_number', '8281412432'),
            'bank_name': data.get('bank_name', 'Moniepoint MFB'),
            'account_name': data.get('account_name', 'Radiant Hope Media')
        }
        
        donation_table.put_item(Item=donation_info)
        return jsonify({'message': 'Donation information updated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/involved/volunteer', methods=['POST'])
def submit_volunteer_form():
    """Submit volunteer application"""
    try:
        data = request.json
        volunteer_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        volunteer = {
            'id': volunteer_id,
            'name': data.get('name'),
            'email': data.get('email'),
            'phone': data.get('phone'),
            'skills': data.get('skills'),
            'availability': data.get('availability'),
            'message': data.get('message'),
            'submitted_at': timestamp
        }
        
        volunteer_table.put_item(Item=volunteer)
        return jsonify({'message': 'Volunteer application submitted successfully', 'volunteer_id': volunteer_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/involved/volunteer', methods=['GET'])
def get_volunteer_applications():
    """Get all volunteer applications"""
    try:
        response = volunteer_table.scan()
        items = response.get('Items', [])
        
        # Sort by submission time (newest first)
        items.sort(key=lambda x: x.get('submitted_at', ''), reverse=True)
        
        return jsonify({'applications': items})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/involved/partner', methods=['POST'])
def submit_partnership_form():
    """Submit partnership request"""
    try:
        data = request.json
        partner_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        partnership = {
            'id': partner_id,
            'organization_name': data.get('organization_name'),
            'contact_name': data.get('contact_name'),
            'email': data.get('email'),
            'phone': data.get('phone'),
            'partnership_type': data.get('partnership_type'),
            'message': data.get('message'),
            'submitted_at': timestamp
        }
        
        partner_table.put_item(Item=partnership)
        return jsonify({'message': 'Partnership request submitted successfully', 'partner_id': partner_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/involved/partner', methods=['GET'])
def get_partnership_requests():
    """Get all partnership requests"""
    try:
        response = partner_table.scan()
        items = response.get('Items', [])
        
        # Sort by submission time (newest first)
        items.sort(key=lambda x: x.get('submitted_at', ''), reverse=True)
        
        return jsonify({'partnerships': items})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Utility functions for DynamoDB table creation
def create_tables():
    """Create DynamoDB tables if they don't exist"""
    tables = [
        {
            'TableName': os.getenv('BLOG_TABLE_NAME', 'blog_posts'),
            'KeySchema': [{'AttributeName': 'id', 'KeyType': 'HASH'}],
            'AttributeDefinitions': [{'AttributeName': 'id', 'AttributeType': 'S'}],
            'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
        },
        {
            'TableName': os.getenv('FEATURED_TABLE_NAME', 'featured_posts'),
            'KeySchema': [{'AttributeName': 'id', 'KeyType': 'HASH'}],
            'AttributeDefinitions': [{'AttributeName': 'id', 'AttributeType': 'S'}],
            'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
        },
        {
            'TableName': os.getenv('CONTACT_TABLE_NAME', 'contact_submissions'),
            'KeySchema': [{'AttributeName': 'id', 'KeyType': 'HASH'}],
            'AttributeDefinitions': [{'AttributeName': 'id', 'AttributeType': 'S'}],
            'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
        },
        {
            'TableName': os.getenv('DONATION_TABLE_NAME', 'donation_info'),
            'KeySchema': [{'AttributeName': 'id', 'KeyType': 'HASH'}],
            'AttributeDefinitions': [{'AttributeName': 'id', 'AttributeType': 'S'}],
            'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
        },
        {
            'TableName': os.getenv('VOLUNTEER_TABLE_NAME', 'volunteer_applications'),
            'KeySchema': [{'AttributeName': 'id', 'KeyType': 'HASH'}],
            'AttributeDefinitions': [{'AttributeName': 'id', 'AttributeType': 'S'}],
            'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
        },
        {
            'TableName': os.getenv('PARTNER_TABLE_NAME', 'partnership_requests'),
            'KeySchema': [{'AttributeName': 'id', 'KeyType': 'HASH'}],
            'AttributeDefinitions': [{'AttributeName': 'id', 'AttributeType': 'S'}],
            'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
        }
    ]
    
    existing_tables = [table.name for table in dynamodb.tables.all()]
    
    for table_def in tables:
        table_name = table_def['TableName']
        if table_name not in existing_tables:
            try:
                dynamodb.create_table(
                    TableName=table_def['TableName'],
                    KeySchema=table_def['KeySchema'],
                    AttributeDefinitions=table_def['AttributeDefinitions'],
                    ProvisionedThroughput=table_def['ProvisionedThroughput']
                )
                print(f"Table {table_name} created successfully")
            except Exception as e:
                print(f"Error creating table {table_name}: {str(e)}")

# Seed data function (for development purposes)
def seed_initial_data():
    """Seed initial data into DynamoDB tables"""
    # Sample blog posts
    blog_data = [
        {
            'id': str(uuid.uuid4()),
            'title': 'AI and Machine Learning In Vulnerability Management',
            'date': 'Dec 17, 2024',
            'img': '/assets/images/homepage/blog.png',
            'tag': 'Industrial Cybersecurity',
            'content': 'This is a sample blog post about AI and Machine Learning in vulnerability management.',
            'author': 'John Doe',
            'read_time': '5 min',
            'likes': 42,
            'comments_count': 7
        },
        {
            'id': str(uuid.uuid4()),
            'title': 'Renewable Energy Trends',
            'date': 'Jan 10, 2025',
            'img': '/assets/images/homepage/blog.png',
            'tag': 'Industrial Cybersecurity',
            'content': 'This is a sample blog post about renewable energy trends.',
            'author': 'Jane Smith',
            'read_time': '3 min',
            'likes': 28,
            'comments_count': 5
        },
        {
            'id': str(uuid.uuid4()),
            'title': 'Advancements in Robotics',
            'date': 'Feb 5, 2025',
            'img': '/assets/images/homepage/blog.png',
            'tag': 'Industrial Cybersecurity',
            'content': 'This is a sample blog post about advancements in robotics.',
            'author': 'David Johnson',
            'read_time': '7 min',
            'likes': 35,
            'comments_count': 10
        }
    ]
    
    # Sample featured posts
    featured_data = [
        {
            'id': str(uuid.uuid4()),
            'title': 'Protecting the Chain: Understanding and Adressing Supply Chain Vulnerabilities in Cybersecurity',
            'date': 'Dec 17, 2024',
            'img': '/assets/images/homepage/blog2.png',
            'tag': 'Industrial Cybersecurity',
            'author': 'Michael Brown'
        },
        {
            'id': str(uuid.uuid4()),
            'title': 'OPSWAT Academy Welcomes AIIPLtech as the First Partner in Its Reseller Training Program',
            'date': 'Jan 10, 2025',
            'img': '/assets/images/homepage/blog2.png',
            'tag': 'Academy News',
            'author': 'Sarah Wilson'
        },
        {
            'id': str(uuid.uuid4()),
            'title': 'Zero-Trust Architecture in Operational Technology: A Paradigm Shift for Enhanced Security',
            'date': 'Feb 5, 2025',
            'img': '/assets/images/homepage/blog2.png',
            'tag': 'Industrial Cybersecurity',
            'author': 'Robert Davis'
        }
    ]
    
    # Sample donation info
    donation_data = {
        'id': 'donation-info-001',
        'account_number': '8281412432',
        'bank_name': 'Moniepoint MFB',
        'account_name': 'Radiant Hope Media'
    }
    
    # Insert blog posts
    for post in blog_data:
        try:
            blog_table.put_item(Item=post)
        except Exception as e:
            print(f"Error inserting blog post: {str(e)}")
    
    # Insert featured posts
    for post in featured_data:
        try:
            featured_table.put_item(Item=post)
        except Exception as e:
            print(f"Error inserting featured post: {str(e)}")
    
    # Insert donation info
    try:
        donation_table.put_item(Item=donation_data)
    except Exception as e:
        print(f"Error inserting donation info: {str(e)}")

# Additional utility function
def check_dynamo_connection():
    """Check if we can connect to DynamoDB"""
    try:
        tables = list(dynamodb.tables.all())
        return True
    except Exception as e:
        print(f"Error connecting to DynamoDB: {str(e)}")
        return False

@app.route('/api/health', methods=['GET'])
def health_check():
    """API health check endpoint"""
    db_status = "connected" if check_dynamo_connection() else "disconnected"
    return jsonify({
        'status': 'ok',
        'database': db_status,
        'timestamp': datetime.now().isoformat()
    })

import os  

if __name__ == '__main__':  
    # Check database connection  
    if check_dynamo_connection():  
        print("Connected to DynamoDB successfully!")  
    else:  
        print("Failed to connect to DynamoDB. Please check your credentials and network.")  
    
    # Uncomment to create tables and seed data when needed  
        #create_tables()  
        #seed_initial_data()  

    port = int(os.environ.get('PORT', 5000))  
    app.run(host='0.0.0.0', port=port)  
