# CodeLabX - UI Plan

## Design Philosophy

**Principles**:
- Clean, minimalist interface focused on learning
- Mobile-responsive design using Bootstrap 5
- Consistent navigation and user experience
- Progress-focused visual feedback
- Accessible and inclusive design

**Color Scheme**:
- Primary: Deep Blue (#2c3e50)
- Secondary: Emerald Green (#27ae60) for success/completion
- Accent: Orange (#e67e22) for highlights
- Background: Light Gray (#f8f9fa)
- Text: Dark Gray (#343a40)

**Typography**:
- Headings: Bootstrap default font stack
- Body: System fonts for performance
- Code: Monospace font for code snippets

## Navigation Structure

### Main Navigation Bar
**Location**: Fixed top navigation

**Components**:
- Logo/Brand name (left)
- Navigation links (center)
  - Dashboard
  - Roadmaps
  - Content Library
  - Progress
- User menu (right)
  - Profile dropdown
  - Settings
  - Logout

**States**:
- Active page highlighting
- Responsive hamburger menu for mobile
- Sticky on scroll

### Secondary Navigation
**Context**: Page-specific navigation

**Roadmap Navigation**:
- Breadcrumb: Home > Roadmaps > [Roadmap Name]
- Day selector: Day 1 | Day 2 | Day 3 | ...
- Progress indicator: 3/30 days completed

**Content Navigation**:
- Topic filter: All | DSA | ML | AI | DS
- Difficulty filter: All | Beginner | Intermediate | Advanced
- Search bar

## Page Layouts

### 1. Landing Page
**URL**: `/`

**Purpose**: Welcome page for non-authenticated users

**Sections**:
- Hero section with value proposition
- Feature highlights (roadmaps, progress tracking, assessments)
- How it works (3-step process)
- Topic preview cards
- Call-to-action (Sign up button)
- Footer with links

**Components**:
- Hero banner with illustration
- Feature cards with icons
- Topic preview cards
- Sign up form (or link to registration)
- Testimonials (future)

### 2. Registration Page
**URL**: `/register/`

**Purpose**: New user registration

**Layout**:
- Centered card layout
- Form fields:
  - Username
  - Email
  - Password
  - Confirm Password
- Form validation
- Link to login page
- Terms and conditions checkbox

**Components**:
- Registration form
- Password strength indicator
- Form validation messages
- Social login buttons (future)

### 3. Login Page
**URL**: `/login/`

**Purpose**: User authentication

**Layout**:
- Centered card layout
- Form fields:
  - Username/Email
  - Password
- Remember me checkbox
- Forgot password link
- Link to registration page

**Components**:
- Login form
- Remember me checkbox
- Forgot password link
- Social login buttons (future)

### 4. User Dashboard
**URL**: `/dashboard/`

**Purpose**: Main user hub showing progress and activity

**Layout**:
- **Header**: Welcome message with user name
- **Main Content Grid**:
  - **Left Column (60%)**:
    - Current roadmap card
    - Today's learning tasks
    - Recent activity feed
  - **Right Column (40%)**:
    - Activity heatmap (GitHub-style)
    - Progress overview cards
    - Achievements display
    - Quick actions

**Components**:
- Welcome header
- Current roadmap card with progress bar
- Today's tasks list with checkboxes
- Activity heatmap (7-day, 30-day views)
- Progress cards (days completed, quizzes passed, projects done)
- Achievement badges
- Quick action buttons (new roadmap, continue learning, take quiz)

### 5. Roadmap List Page
**URL**: `/roadmaps/`

**Purpose**: Display all user roadmaps

**Layout**:
- Page header with "Create New Roadmap" button
- Grid of roadmap cards
- Filter options (active, completed, archived)

**Components**:
- Page header with action button
- Roadmap cards showing:
  - Topic icon and name
  - Progress bar
  - Days completed/total
  - Status badge
  - Last activity date
  - Action buttons (continue, edit, delete)
- Filter dropdown
- Search bar

### 6. Create Roadmap Page
**URL**: `/roadmaps/create/`

**Purpose**: Form to create new learning roadmap

**Layout**:
- Centered form layout
- Multi-step form (optional)

**Form Fields**:
- Topic selection (dropdown with icons)
- Duration in months (slider or input)
- Daily study hours (slider or input)
- Difficulty level (radio buttons)
- Start date (date picker)
- Optional notes

**Components**:
- Topic selection cards with descriptions
- Duration slider with visual feedback
- Study hours input
- Difficulty level selector
- Preview section showing estimated roadmap
- Create button
- Cancel button

### 7. Roadmap Detail Page
**URL**: `/roadmaps/<id>/`

**Purpose**: Overview of specific roadmap

**Layout**:
- **Header**: Roadmap title and progress
- **Main Content**:
  - Roadmap timeline visualization
  - Day cards grid
  - Statistics sidebar

**Components**:
- Roadmap header with progress bar
- Topic icon and description
- Statistics cards (total days, hours spent, completion %)
- Day cards grid:
  - Day number
  - Day title
  - Topics covered
  - Completion status
  - Estimated time
  - Action button (start, continue, review)
- Edit/Delete buttons
- Share button (future)

### 8. Daily Learning Page
**URL**: `/roadmaps/<id>/day/<day_number>/`

**Purpose**: Display content for a specific day

**Layout**:
- **Header**: Day title and progress
- **Navigation**: Previous/Next day buttons
- **Content Sections**:
  - Theory content
  - Visual explanations
  - Practice tasks
  - Projects (if applicable)
- **Sidebar**: Day progress and resources

**Components**:
- Day header with progress indicator
- Navigation buttons (previous/next day)
- Theory content section with expandable sections
- Visual content carousel or grid
- Practice tasks list with:
  - Task description
  - Starter code (if applicable)
  - Solution toggle
  - Completion checkbox
- Project section (if applicable)
- Mark complete button
- Timer (optional)
- Notes section (future)

### 9. Content Library Page
**URL**: `/content/`

**Purpose**: Browse all educational content

**Layout**:
- **Header**: Search bar and filters
- **Main Content**: Content cards grid
- **Sidebar**: Topic and difficulty filters

**Components**:
- Search bar
- Topic filter buttons
- Difficulty filter dropdown
- Content cards showing:
  - Topic icon
  - Title
  - Difficulty badge
  - Estimated time
  - Preview text
  - Bookmark button (future)
- Pagination
- Sort options (newest, popular, alphabetical)

### 10. Content Detail Page
**URL**: `/content/<id>/`

**Purpose**: Display specific content piece

**Layout**:
- **Header**: Content title and metadata
- **Main Content**:
  - Theory text
  - Visual explanations
  - Related content
- **Sidebar**: Table of contents and related links

**Components**:
- Content header with topic and difficulty
- Table of contents (sticky sidebar)
- Theory content with syntax highlighting
- Visual content gallery
- Code examples with copy button
- Related content links
- Back to library button
- Add to roadmap button (future)

### 11. Quiz List Page
**URL**: `/quizzes/`

**Purpose**: Display available quizzes

**Layout**:
- Grid of quiz cards
- Filter by topic and difficulty

**Components**:
- Quiz cards showing:
  - Topic icon
  - Quiz title
  - Question count
  - Time limit
  - Difficulty badge
  - Best score (if taken)
  - Start/Retake button
- Filter options
- Search bar

### 12. Quiz Taking Page
**URL**: `/quizzes/<id>/take/`

**Purpose**: Interface for taking a quiz

**Layout**:
- **Header**: Quiz title and timer
- **Main Content**: Question display
- **Sidebar**: Question navigation

**Components**:
- Quiz header with timer (if time limit)
- Progress bar (question X of Y)
- Question display with:
  - Question text
  - Answer options (radio buttons or checkboxes)
  - Navigation buttons (previous, next, submit)
- Question navigation sidebar
- Submit quiz button
- Warning before submit

### 13. Quiz Results Page
**URL**: `/quizzes/<id>/results/<attempt_id>/`

**Purpose**: Display quiz results

**Layout**:
- **Header**: Score and pass/fail status
- **Main Content**: Question review
- **Sidebar**: Performance analytics

**Components**:
- Results header with score circle
- Pass/fail badge
- Time taken
- Question review with:
  - Question text
  - User answer
  - Correct answer
  - Explanation
- Performance analytics:
  - Score breakdown by topic
  - Time per question
  - Comparison with average (future)
- Retake quiz button
- Back to quizzes button

### 14. User Profile Page
**URL**: `/profile/`

**Purpose**: View and edit user profile

**Layout**:
- **Header**: Profile picture and basic info
- **Tabs**: Profile, Preferences, Settings

**Profile Tab**:
- Profile picture with upload
- Name and bio
- Learning statistics
- Achievements

**Preferences Tab**:
- Learning preferences form
- Notification settings
- Theme selection (future)

**Settings Tab**:
- Account settings
- Privacy settings
- Delete account option

**Components**:
- Profile picture with upload button
- Editable profile fields
- Statistics cards
- Achievement badges grid
- Preferences form
- Settings form
- Save buttons

### 15. Progress Page
**URL**: `/progress/`

**Purpose**: Detailed progress analytics

**Layout**:
- **Header**: Overall progress summary
- **Main Content**:
  - Activity heatmap (large)
  - Progress charts
  - Detailed statistics

**Components**:
- Overall progress header with percentage
- Large activity heatmap (year view)
- Progress charts:
  - Learning hours per week
  - Quiz scores over time
  - Topics completed
- Detailed statistics table
- Export data button (future)
- Print report button (future)

### 16. Admin Dashboard
**URL**: `/admin/`

**Purpose**: Django admin for content management

**Layout**:
- Standard Django admin layout
- Custom admin dashboard with:
  - Quick stats
  - Recent content
  - User activity

**Components**:
- Custom admin dashboard
- Quick action buttons
- Statistics cards
- Recent activity list
- Standard Django admin interfaces

## UI Components

### Buttons
**Primary Button**: Solid color, rounded corners
**Secondary Button**: Outline style
**Success Button**: Green for completion
**Danger Button**: Red for destructive actions
**Icon Buttons**: For actions like edit, delete, bookmark

### Cards
**Content Card**: Shadow, rounded corners, hover effect
**Progress Card**: With progress bar
**Stat Card**: Large number, label, icon
**Achievement Card**: Badge icon, title, date earned

### Forms
**Input Fields**: Bootstrap styled with focus states
**Select Dropdowns**: Custom styled
**Checkboxes/Radio Buttons**: Custom styled
**Sliders**: For duration and hours input
**Date Pickers**: Bootstrap datepicker

### Navigation
**Breadcrumb**: Home > Category > Page
**Tabs**: For multi-section pages
**Pagination**: For content lists
**Step Indicator**: For multi-step forms

### Feedback
**Alerts**: Success, warning, error messages
**Tooltips**: For additional information
**Modals**: For confirmations and quick actions
**Loading States**: Spinners for async operations
**Empty States**: Illustrations when no content

### Progress Indicators
**Progress Bars**: Linear, percentage-based
**Circular Progress**: For quiz scores
**Step Progress**: For multi-step processes
**Heatmap**: GitHub-style activity grid

### Data Display
**Tables**: For statistics and lists
**Charts**: For progress visualization (Chart.js)
**Badges**: For status and difficulty
**Tags**: For topics and categories

## Responsive Design

### Breakpoints
- **Mobile**: < 576px
- **Tablet**: 576px - 992px
- **Desktop**: > 992px

### Mobile Adaptations
- Hamburger menu for navigation
- Stacked card layouts
- Simplified dashboard
- Touch-friendly buttons
- Reduced content density

### Tablet Adaptations
- Adjusted grid layouts
- Optimized touch targets
- Simplified navigation

## Accessibility

### Features
- Keyboard navigation support
- Screen reader compatibility
- High contrast mode support
- Focus indicators
- Alt text for images
- ARIA labels for interactive elements
- Skip to content link

### Standards
- WCAG 2.1 AA compliance
- Semantic HTML
- Proper heading hierarchy
- Color contrast ratios > 4.5:1

## Interactive Elements

### Micro-interactions
- Button hover effects
- Card hover lift
- Progress bar animations
- Smooth transitions
- Loading animations
- Success checkmarks

### User Feedback
- Form validation messages
- Success notifications
- Error alerts
- Confirmation modals
- Progress indicators

## Future UI Enhancements

### Phase 2
- Dark mode theme
- Custom theme selection
- Advanced filtering options
- Drag-and-drop roadmap builder
- Interactive code editor
- Real-time collaboration features

### Phase 3
- Mobile app UI patterns
- Gesture-based navigation
- Voice commands
- AR/VR visualizations
- Advanced analytics dashboards

## Design System

### Spacing
- Base unit: 8px
- Consistent padding/margins
- Grid-based layouts

### Typography Scale
- Headings: 24px, 20px, 16px
- Body: 14px, 16px
- Small: 12px

### Border Radius
- Cards: 8px
- Buttons: 4px
- Inputs: 4px

### Shadows
- Card shadow: subtle
- Hover shadow: medium
- Modal shadow: heavy

## Iconography

### Icon Library
- Bootstrap Icons (primary)
- FontAwesome (secondary, if needed)

### Icon Usage
- Consistent sizing (16px, 24px, 32px)
- Semantic meaning
- Color coding by context

## Performance Considerations

### Optimization
- Lazy loading for images
- Minified CSS/JS
- Optimized font loading
- Critical CSS inline
- Image compression

### Loading Strategy
- Progressive enhancement
- Skeleton screens
- Optimistic UI updates
- Caching strategies

## Browser Support

### Target Browsers
- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)
- Mobile browsers (iOS Safari, Chrome Mobile)

### Fallbacks
- Graceful degradation
- Polyfills if needed
- Alternative layouts for older browsers
