import { createBrowserRouter, Navigate } from 'react-router'
import AdminPage from '@/pages/admin/AdminPage'
import LoginPage from '@/pages/LoginPage'
import NotFoundPage from '@/pages/NotFoundPage'
import ParentPage from '@/pages/parent/ParentPage'
import StudentPage from '@/pages/student/StudentPage'
import TeacherPage from '@/pages/teacher/TeacherPage'

export const router = createBrowserRouter([
  { path: '/', element: <Navigate to="/login" replace /> },
  { path: '/login', element: <LoginPage /> },
  { path: '/student', element: <StudentPage /> },
  { path: '/teacher', element: <TeacherPage /> },
  { path: '/parent', element: <ParentPage /> },
  { path: '/admin', element: <AdminPage /> },
  { path: '*', element: <NotFoundPage /> },
])
