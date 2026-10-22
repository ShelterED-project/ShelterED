import { createBrowserRouter } from 'react-router'
import AdminPage from '@/pages/admin/AdminPage'
import LandingPage from '@/pages/landing/LandingPage'
import LoginPage from '@/pages/login/LoginPage'
import NotFoundPage from '@/pages/not-found/NotFoundPage'
import ParentPage from '@/pages/parent/ParentPage'
import RegisterPage from '@/pages/register/RegisterPage'
import ShelterModePage from '@/pages/shelter/ShelterModePage'
import StudentPage from '@/pages/student/StudentPage'
import TeacherPage from '@/pages/teacher/TeacherPage'
import RootLayout from './RootLayout'

export const router = createBrowserRouter([
  {
    element: <RootLayout />,
    children: [
      { path: '/', element: <LandingPage /> },
      { path: '/login', element: <LoginPage /> },
      { path: '/register', element: <RegisterPage /> },
      { path: '/student', element: <StudentPage /> },
      { path: '/shelter', element: <ShelterModePage /> },
      { path: '/teacher', element: <TeacherPage /> },
      { path: '/parent', element: <ParentPage /> },
      { path: '/admin', element: <AdminPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
])
