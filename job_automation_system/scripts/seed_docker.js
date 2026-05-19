use("job_automation");

db.students.deleteMany({});

db.students.insertMany([
  {
    student_id: "STU001",
    name: "John Doe",
    email: "john.doe@example.com",
    phone: "+91-9876543210",
    location: "Bangalore",
    skills: ["python", "django", "react", "javascript", "sql"],
    preferred_locations: ["Bangalore", "Hyderabad"],
    candidate_titles: ["Python Developer", "Backend Developer"],
    active: true,
    created_at: new Date(),
    updated_at: new Date(),
    credentials: {
      naukri: {email: "john.doe@naukri.com", password: "testpass123"},
      linkedin: {email: "john.doe.linkedin@gmail.com", password: "testpass123"},
      foundit: {email: "john.doe@foundit.in", password: "testpass123"}
    }
  },
  {
    student_id: "STU002",
    name: "Jane Smith",
    email: "jane.smith@example.com",
    phone: "+91-9876543211",
    location: "Hyderabad",
    skills: ["java", "spring", "react", "mysql"],
    preferred_locations: ["Hyderabad", "Bangalore"],
    candidate_titles: ["Java Developer", "Backend Engineer"],
    active: true,
    created_at: new Date(),
    updated_at: new Date(),
    credentials: {
      naukri: {email: "jane.smith@naukri.com", password: "testpass123"},
      linkedin: {email: "jane.smith.linkedin@gmail.com", password: "testpass123"},
      foundit: {email: "jane.smith@foundit.in", password: "testpass123"}
    }
  }
]);

print("Inserted:", db.students.countDocuments(), "students");