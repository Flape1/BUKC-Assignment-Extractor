#!/usr/bin/env python
# coding: utf-8

import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import StaleElementReferenceException
import time
from bs4 import BeautifulSoup
import pandas as pd
import urllib.parse
import base64

# Initialize session state variables
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'assignments' not in st.session_state:
    st.session_state.assignments = []
if 'driver' not in st.session_state:
    st.session_state.driver = None

def create_webdriver():
    # Configure Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-infobars")
    
    # Setup the webdriver
    driver = webdriver.Chrome(options=chrome_options)
    return driver

# CMS Login URL
cms_url = "https://cms.bahria.edu.pk/Logins/Student/Login.aspx"
lms_url = "https://lms.bahria.edu.pk/Student/Assignments.php"

# Step 1: Login to CMS
def login_to_cms(wait, driver, username, password):
    driver.get(cms_url)
    time.sleep(2)
    
    # Wait for the enrollment field to be visible before interacting with it
    enrollment_field = wait.until(EC.visibility_of_element_located((By.ID, "BodyPH_tbEnrollment")))
    enrollment_field.send_keys(username)

    # Wait for the password field to be visible
    password_field = wait.until(EC.visibility_of_element_located((By.ID, "BodyPH_tbPassword")))
    password_field.send_keys(password)

    # For Campus selection
    institute_dropdown = wait.until(EC.visibility_of_element_located((By.ID, "BodyPH_ddlInstituteID")))
    select_institute = Select(institute_dropdown)
    select_institute.select_by_visible_text("Karachi Campus")

    # For Role selection (if not default)
    role_dropdown = wait.until(EC.visibility_of_element_located((By.ID, "BodyPH_ddlSubUserType")))
    select_role = Select(role_dropdown)
    select_role.select_by_visible_text("Student")

    driver.find_element(By.ID, "BodyPH_btnLogin").click()
    time.sleep(2)  # Wait for the login to complete
    return True

# Step 2: Navigate to LMS and open Assignments
def navigate_to_lms(driver):
    driver.get("https://cms.bahria.edu.pk/Sys/Common/GoToLMS.aspx")
    time.sleep(2)  # Wait for LMS to load

# Function to download a file
def download_file(driver, file_url):
    driver.get(file_url)
    time.sleep(3)  # Wait for the file to load
    try:
        # Get the HTML content after navigating to file URL
        page_source = driver.page_source
        # Check if it's a binary file or HTML page
        if '<html' not in page_source[:100]:  # Likely a binary file download
            return driver.page_source  # Return binary content
        else:
            # It's still an HTML page, look for download links
            soup = BeautifulSoup(page_source, 'html.parser')
            download_links = soup.find_all('a', href=True)
            for link in download_links:
                if 'download' in link.get('href').lower() or '.pdf' in link.get('href').lower() or '.doc' in link.get('href').lower():
                    absolute_url = urllib.parse.urljoin(file_url, link.get('href'))
                    driver.get(absolute_url)
                    time.sleep(2)
                    return driver.page_source
    except Exception as e:
        print(f"Error downloading file: {e}")
    return None

# Step 3: Extract assignments for a given course
def extract_assignments(driver):
    assignments_data = []

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    assignments_table = soup.find("table")
    
    if not assignments_table:
        print("No assignments found for this course.")
        return []

    rows = assignments_table.find_all("tr")[1:]

    for row in rows:
        cells = row.find_all("td")
        if len(cells) > 6:  # Ensure there are enough columns
            assignment_name = cells[1].text.strip()
            deadline = cells[7].text.strip()
            if cells[6].text.strip() == "Deadline Exceeded":
                continue
            
            # Extract the download link from cell[2]
            download_link_tag = cells[2].find('a', href=True)
            if download_link_tag:
                # Get the absolute URL for download
                download_link = download_link_tag.get('href', '')
                if download_link:
                    # Make sure the link is absolute
                    if not download_link.startswith('http'):
                        # Create absolute URL
                        base_url = "https://lms.bahria.edu.pk/Student/"
                        download_link = urllib.parse.urljoin(base_url, download_link)
                else:
                    download_link = None
            else:
                download_link = None

            assignments_data.append({
                "Assignment": assignment_name,
                "Deadline": deadline,
                "Download Link": download_link
            })
    
    return assignments_data

# Step 4: Extract assignments for all courses
def extract_all_courses(wait, driver):
    driver.get(lms_url)
    time.sleep(2)

    all_assignments = []
    progress_text = st.empty()

    # Refresh the dropdown options each time to avoid stale references
    while True:
        try:
            course_dropdown = wait.until(EC.presence_of_element_located((By.NAME, "courseName")))
            select = Select(course_dropdown)
            options = [option.text.strip() for option in select.options if option.text.strip() and option.text.strip() != "Select Course"]
            break  # Break the loop if the dropdown is successfully located
        except StaleElementReferenceException:
            continue  # Retry if the element went stale

    # Create progress bar
    progress_bar = st.progress(0)
    total_courses = len(options)
    
    # Iterate through all courses
    for i, course_name in enumerate(options):
        progress_text.write(f"Fetching assignments for: {course_name}")
        progress_value = int((i / total_courses) * 100)
        progress_bar.progress(progress_value)

        # Refresh dropdown each time to prevent stale element issues
        course_dropdown = wait.until(EC.presence_of_element_located((By.NAME, "courseName")))
        select = Select(course_dropdown)
        
        try:
            select.select_by_visible_text(course_name)
            time.sleep(0.5)  # Give it some time to load the assignments page

            # Extract assignments
            assignments = extract_assignments(driver)
            for assignment in assignments:
                assignment["Course"] = course_name
                all_assignments.append(assignment)

        except StaleElementReferenceException:
            progress_text.write(f"Stale element encountered. Retrying for course: {course_name}")
            continue  # Retry with the next course if the dropdown goes stale
    
    progress_bar.progress(100)
    progress_text.write("All assignments extracted successfully!")
    time.sleep(1)
    progress_text.empty()
    
    return all_assignments

def get_download_link_html(filename, file_content, button_text="Download Assignment"):
    """Generate HTML for a download button"""
    if file_content is None:
        return ""
    
    b64 = base64.b64encode(file_content.encode()).decode()
    download_link = f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}" class="download-button">{button_text}</a>'
    return download_link

def download_assignment(url, driver):
    """Download an assignment file using the WebDriver"""
    try:
        # Navigate to the assignment URL
        driver.get(url)
        time.sleep(2)  # Wait for page to load
        
        # Get the page source
        content = driver.page_source
        
        # Get filename from URL
        filename = url.split('/')[-1]
        if '?' in filename:
            filename = filename.split('?')[0]
        
        # If no extension or looks like a PHP file, add .pdf extension
        if '.' not in filename or filename.endswith('.php'):
            filename = f"assignment_{int(time.time())}.pdf"
            
        return filename, content
    except Exception as e:
        st.error(f"Error downloading file: {e}")
        return None, None

# Main program
def run():
    # Set page config and custom theme
    st.set_page_config(
        page_title="BUKC Assignment Extractor",
        page_icon="📚",
        layout="wide"
    )
    
    # Dark theme styling
    st.markdown("""
    <style>
        .stApp {
            background-color: #2c3e50;
            color: #ecf0f1;
        }
        
        h1, h2, h3 {
            color: #ecf0f1;
        }
        
        /* Improve expander styling */
        .streamlit-expanderHeader {
            background-color: #34495e !important;
            color: #ecf0f1 !important;
            border-radius: 5px !important;
        }
        
        /* Change hover color for login button */
        .stButton > button {
            background-color: #3498db !important;
            color: white !important;
            border-radius: 5px !important;
            border: none !important;
            padding: 0.5rem 1rem !important;
            font-weight: bold !important;
        }
        
        .stButton > button:hover {
            background-color: #2980b9 !important;
            color: white !important;
        }
        
        /* Security box styling */
        .security-box {
            background-color: #34495e;
            border-left: 4px solid #3498db;
            padding: 10px 15px;
            border-radius: 5px;
            margin-bottom: 20px;
            color: #ecf0f1;
        }
        
        /* Assignment card styling */
        .assignment-card {
            margin-bottom: 1rem;
            padding: 1rem;
            background-color: #34495e;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            border-left: 4px solid #3498db;
            transition: transform 0.2s ease;
            color: #ecf0f1;
        }
        
        .assignment-card:hover {
            transform: translateY(-3px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.3);
        }
        
        /* Download button styling */
        .download-button {
            display: inline-block;
            padding: 0.5rem 1rem;
            background-color: #2ecc71;
            color: white !important;
            text-decoration: none;
            border-radius: 5px;
            margin-top: 0.5rem;
            transition: all 0.3s ease;
            font-weight: bold;
            cursor: pointer;
        }
        
        .download-button:hover {
            background-color: #27ae60;
            color: white !important;
            text-decoration: none;
        }
        
        /* Deadline styling */
        .deadline-text {
            color: #e74c3c;
            font-weight: bold;
        }
        
        /* Custom success box */
        .success-box {
            padding: 10px 15px;
            border-radius: 5px;
            background-color: #27ae60;
            color: white;
            margin-bottom: 10px;
        }
        
        /* Custom error box */
        .error-box {
            padding: 10px 15px;
            border-radius: 5px;
            background-color: #e74c3c;
            color: white;
            margin-bottom: 10px;
        }
        
        /* Form background */
        .stForm {
            background-color: #34495e;
            padding: 20px;
            border-radius: 10px;
        }
        
        /* Override some Streamlit defaults */
        .css-1d391kg, .css-12oz5g7 {
            background-color: #2c3e50;
        }
        
        /* Input fields */
        .stTextInput > div > div > input {
            background-color: #34495e;
            color: #ecf0f1;
            border-color: #3498db;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.title('Bahria University Assignment Extractor')
    
    # Add security note with improved styling
    st.markdown("""
    <div class="security-box">
        <p>🔒 <strong>Security Note:</strong> This app does not store your password or any login credentials. All data is processed in real-time and is not saved anywhere.</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Login section
    if not st.session_state.logged_in:
        with st.form("login_form"):
            st.subheader("Login to CMS")
            st.markdown("""
            <div style='margin-bottom: 1.5rem; color: #ecf0f1;'>
                Please enter your CMS credentials to view your assignments.
            </div>
            """, unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            with col1:
                username = st.text_input("Enter Enrollment Number", placeholder="e.g., 12345")
            with col2:
                password = st.text_input("Enter Password", type="password", placeholder="Enter your password")
            
            submit_button = st.form_submit_button("Login & Extract Assignments")
            
            if submit_button:
                if username and password:
                    with st.spinner("Logging in and extracting assignments..."):
                        try:
                            driver = create_webdriver()
                            wait = WebDriverWait(driver, 10)
                            
                            # Login to CMS
                            login_status = login_to_cms(wait, driver, username, password)
                            
                            if login_status:
                                # Navigate to LMS and extract assignments
                                navigate_to_lms(driver)
                                assignments = extract_all_courses(wait, driver)
                                
                                # Store assignments in session state
                                st.session_state.assignments = assignments
                                st.session_state.logged_in = True
                                st.session_state.driver = driver
                                
                                # Force page rerun to show assignments
                                st.rerun()
                            else:
                                st.error("Login failed. Please check your credentials.")
                                if 'driver' in locals():
                                    driver.quit()
                        except Exception as e:
                            st.error(f"An error occurred: {e}")
                            if 'driver' in locals():
                                driver.quit()
                else:
                    st.warning("Please enter your enrollment number and password.")
    
    # Display assignments if logged in
    else:
        # Add logout button with improved styling
        col1, col2 = st.columns([1, 6])
        with col1:
            if st.button("Logout", key="logout_button"):
                if st.session_state.driver:
                    st.session_state.driver.quit()
                st.session_state.driver = None
                st.session_state.logged_in = False
                st.session_state.assignments = []
                st.rerun()
        
        if st.session_state.assignments:
            # Convert to DataFrame for easier handling
            df = pd.DataFrame(st.session_state.assignments)
            
            # Display assignments grouped by course with improved styling
            st.subheader("Your Assignments")
            
            # Group by course and display
            courses = df['Course'].unique()
            
            for course in courses:
                with st.expander(f"📚 {course}", expanded=True):
                    course_assignments = df[df['Course'] == course]
                    
                    for i, row in course_assignments.iterrows():
                        download_url = row['Download Link'] if pd.notna(row['Download Link']) else None
                        assignment_name = row['Assignment']
                        
                        # Create a unique key for each button
                        button_key = f"download_button_{i}_{assignment_name.replace(' ', '_')}"
                        
                        st.markdown(f"""
                        <div class="assignment-card">
                            <div style='margin-bottom: 0.5rem;'>
                                <strong>Assignment:</strong> {assignment_name}
                            </div>
                            <div style='margin-bottom: 0.5rem;'>
                                <strong>Deadline:</strong> <span class="deadline-text">{row['Deadline']}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        if download_url:
                            if st.button(f"📥 Download {assignment_name}", key=button_key):
                                if st.session_state.driver is None:
                                    st.error("Session expired. Please log in again.")
                                    st.session_state.logged_in = False
                                    st.session_state.assignments = []
                                    st.rerun()
                                    return
                                    
                                with st.spinner(f"Downloading {assignment_name}..."):
                                    try:
                                        st.session_state.driver.get(download_url)
                                        time.sleep(2)  # Wait for page to load
                                        
                                        # Try to find actual file download link
                                        current_url = st.session_state.driver.current_url
                                        page_source = st.session_state.driver.page_source
                                        soup = BeautifulSoup(page_source, 'html.parser')
                                        
                                        # Look for common download elements
                                        download_links = []
                                        for a in soup.find_all('a', href=True):
                                            href = a.get('href', '')
                                            if ('download' in href.lower() or 
                                                '.pdf' in href.lower() or 
                                                '.doc' in href.lower() or 
                                                '.zip' in href.lower()):
                                                download_links.append(a)
                                        
                                        if download_links:
                                            # Use the first download link
                                            download_href = download_links[0].get('href')
                                            if not download_href.startswith('http'):
                                                download_href = urllib.parse.urljoin(current_url, download_href)
                                            
                                            # Create download link
                                            filename = download_href.split('/')[-1]
                                            if '?' in filename:
                                                filename = filename.split('?')[0]
                                            
                                            st.markdown(f"""
                                            <div class="success-box">
                                                <p>✅ Ready to download: {filename}</p>
                                                <a href="{download_href}" download="{filename}" class="download-button" target="_blank">
                                                    Click here if download doesn't start automatically
                                                </a>
                                            </div>
                                            <script>
                                                window.open('{download_href}', '_blank');
                                            </script>
                                            """, unsafe_allow_html=True)
                                        else:
                                            # No specific download link found, use the current page
                                            st.markdown(f"""
                                            <div class="success-box">
                                                <p>✅ Download page opened</p>
                                                <a href="{current_url}" class="download-button" target="_blank">
                                                    Click here to open download page in a new tab
                                                </a>
                                            </div>
                                            """, unsafe_allow_html=True)
                                    except Exception as e:
                                        st.error(f"Error downloading assignment: {e}")
                        else:
                            st.info("No download available for this assignment.")
        else:
            st.info("No assignments found.")

if __name__ == "__main__":
    run()