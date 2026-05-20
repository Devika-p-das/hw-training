use companyDB

db.employees.insertOne({
  empId: 101,
  name: "Ravi",
  department: "IT",
  salary: 75000,
  isActive: true
})
db.employees.insertMany([{
empId:102,
name:"Devi",
department:"Mathematics",
salary:80000,
isActive:true
  },
{
  empId: 104,
    name: "Meera",
    department: "Finance",
    salary: 72000,
    isActive: false
  },
  {
    empId: 105,
    name: "Suresh",
    department: "IT",
    salary: 80000,
    isActive: true
  },
  {
    empId: 106,
    name: "Neha",
    department: "Marketing",
    salary: 45000,
    isActive: false
  }
])
db.employees.updateMany(
  { department: "IT" },
  { $mul: { salary: 1.10 } }
)

db.employees.deleteMany({
  isActive: false
})

db.employees.find().pretty()

/// Teminal commandsfor the task2
/// Export JSON
// mongoexport --db=companyDB --collection=employees --out=employees.json

// /Export CSV
// mongoexport --db=companyDB --collection=employees --type=csv --fields=empId,name,department,salary,isActive --out=employees.csv

// /Database Dump
// mongodump --db=companyDB --out=backup

// /Drop Database
//use companyDB
//db.dropDatabase()

/// Restore Database
// mongorestore --db companyDB backup/companyDB

/// Import JSON
// mongoimport --db=companyDB --collection=importedEmployees --file=employees.json