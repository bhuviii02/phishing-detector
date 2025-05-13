from flask import Flask, render_template, request, jsonify
import whois
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import ssl
import socket
import datetime

app = Flask(__name__)

# Mock analysis functions - replace with real implementations
def analyze_url(url):
    # Basic URL pattern analysis
    parsed = urlparse(url)
    suspicious = False
    reasons = []
    
    # Check for IP address instead of domain
    try:
        socket.inet_aton(parsed.netloc.split(':')[0])
        suspicious = True
        reasons.append("Uses IP address instead of domain name")
    except socket.error:
        pass
    
    # Check for @ symbol (might indicate credentials in URL)
    if '@' in url:
        suspicious = True
        reasons.append("Contains @ symbol (possible embedded credentials)")
    
    # Check for subdomains
    if len(parsed.netloc.split('.')) > 3:
        suspicious = True
        reasons.append("Excessive subdomains")
    
    # Check for non-standard ports
    if parsed.port and parsed.port not in [80, 443]:
        suspicious = True
        reasons.append("Uses non-standard port")
    
    return {
        'suspicious': suspicious,
        'reasons': reasons
    }

def check_ssl(url):
    parsed = urlparse(url)
    if not parsed.scheme == 'https':
        return {'valid': False, 'reason': 'No HTTPS'}
    
    hostname = parsed.netloc.split(':')[0]
    context = ssl.create_default_context()
    
    try:
        with socket.create_connection((hostname, 443)) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                
                # Check expiration
                expires = datetime.datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                if expires < datetime.datetime.now():
                    return {'valid': False, 'reason': 'Certificate expired'}
                
                return {'valid': True, 'issuer': cert['issuer'][1][0][1]}
    except Exception as e:
        return {'valid': False, 'reason': str(e)}

def check_domain_age(domain):
    try:
        w = whois.whois(domain)
        if w.creation_date:
            if isinstance(w.creation_date, list):
                creation_date = w.creation_date[0]
            else:
                creation_date = w.creation_date
            
            age = (datetime.datetime.now() - creation_date).days
            return {
                'age_days': age,
                'created': creation_date.strftime('%Y-%m-%d'),
                'new': age < 30  # Consider domains <30 days old as suspicious
            }
    except Exception:
        pass
    return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    url = request.form['url'].strip()
    
    # Perform all analyses
    url_analysis = analyze_url(url)
    ssl_check = check_ssl(url)
    domain = urlparse(url).netloc.split(':')[0]
    domain_age = check_domain_age(domain)
    
    # Determine if phishing
    is_phishing = (
        url_analysis['suspicious'] or
        not ssl_check['valid'] or
        (domain_age and domain_age['new'])
    )
    
    # Prepare results
    results = {
        'url': url,
        'is_phishing': is_phishing,
        'details': {
            'url_analysis': url_analysis,
            'ssl': ssl_check,
            'domain_age': domain_age
        }
    }
    
    return render_template('results.html', results=results)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
