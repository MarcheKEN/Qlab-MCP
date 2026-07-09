# September 2025 QClass 5.5 at the Voxel - Day 2

Source transcript: `September 2025 QClass 5.5 at the Voxel - Day 2.txt`

Welcome
4:50
Today we are going to talk about MIDI, MSC, OSC,  show control for a little bit. We're going to talk
4:59
about video. And that's the main plan. But before  I do that, I was thinking about uh as I came in
5:07
this morning um a couple of things that I alluded  to and then skipped over um talking about object
5:15
audio. So I want to conclude and wrap up the  object audio discussion uh briefly um and um
Object Audio - cue objects and map objects
5:25
talk about cue objects versus map objects because I  started to talk about those things. Good morning.
5:31
Good morning. You missed only some chitchat  there. We there's been no actual schooling
5:36
going on yet. Um I alluded to and then glossed  over cue objects and map objects and I want to fill
5:47
in that space. So if you recall yesterday, we had  this piece of music assigned to this audio cue.
6:00
In the audio cue, in the objects tab, we  created an object. That object moved around
6:11
and with the monitor window for the map  open, the object is visible in the monitor.
6:22
If I use a fade cue to move that object around, we  see the object move in real time on the monitor
6:29
window in the monitor window. But when the  music cue or the music, the cue named music stops,
6:38
the object vanishes because the object that  belongs to the cue only really exists while
6:44
the cue is running. That's sort of something sort of  universally true in QLab. When the cue is running,
6:50
the things that the cue does are part of QLab's  business. But when the cue is not running,
6:56
it is as though there is no such  cue. Sort of. But we have another
7:04
layer of objects available in QLab called map  objects. And these objects belong to the map,
7:12
not to an individual cue. So I'm going to go to  workspace settings. I'm going to go to audio to
7:18
audio maps and I'm going to edit once again this  map over on the left. The marks and filters list
7:28
here um is two tabs uh has has a companion tab  next to it. Map objects. And I'm going to add
7:37
a map object. Map objects are shown as a little  diamond with double letters. Um, for those of you
7:47
uh of approximately my age or older who lived in  New York City, this is how express subway trains
7:52
used to be indicated. Subways have their letters  or numbers in a circle, but express trains had a diamond with a double letter. Um, so that was,  you know, that's just a little fun thing for me.
8:04
A map object belongs to the map. And we're  going to put this map object right there.
8:19
Now when we look at the map in the monitor window  that map object is present. It's always present
8:25
because it belongs to the map and therefore is  always with the map. When I take an audio cue
8:37
and have it use that map,
8:44
when I do nothing else in the objects  tab, the map object is available as
8:50
an output. Double A is available  here. So, if I target some audio,
8:59
let's see. Been doing all music. Let's try  to do something else. Say what? What? Well,
9:14
we can do some rain. Let's do some  rain. What'd you say? What latitude?
9:24
I thought you said what an attitude. I was like  spicy Chris. All right, got some rain here. Uh,
9:32
yes. Sound ideas 6036. Good library for  rain. Um, we're going to take it out of
9:39
the levels tab entirely so that no levels  tab action happens. And in the objects tab,
9:44
we're not going to make a cue object. We're just  going to assign the rain to the map object.
9:55
And now it's raining. If I also created  a cue object or two, those cue objects would
10:02
be available in this matrix mixer with a  gap and then the map object to the right.
10:12
Did you see that? No, I'm sorry. I wasn't  watching. I'm running the cue. I added a
10:18
cue object and then I decided to delete  the cue object and playback stopped for
10:28
the cue but playback keeps going. I  think it's probably because it was
10:35
being routed to a map object. There's  probably a little bug in there. Okay.
10:43
Now, because the map object belongs  to the map and not the cue, I can't select it here. I can't do  anything other than route audio to
10:52
it. If I want to move the map object,  no, hang on. Let me start again. Because
11:00
the thing about the map object is any cue that  uses the map can route to that map object.
11:06
So the map object is sort of at a higher  level of the hierarchy. Any cue using the map
11:11
could send audio there and all those  cues' audio would get mapped would get
11:17
um added together and sent to that object in  that location on the map. So here's some rain.
11:26
And now that you've started me down this path, we'll add a little this rain thunder cue.  Is this the one I think it is? Yes, it is.
11:39
Yeah, we're going to send that  also to the same map object.
11:48
Okay.
11:58
But now if we have say some scene music
12:06
the scene music. This is not a good fit. It's not the right piece of music to go  together. Oh, I didn't loot that.
12:19
The music has its own object right here  that moves around independently. Whatever.
12:29
Both cues that go to the map  object are sitting still. that map object is unaffected by other cues  who come and go. It's unsurprising. But I can
Object Audio - fading map objects
12:43
move the map object using a fade cue. And this is  where we reach back to the beginning of talking
12:50
about the basics tab. I've created a fade cue here.  And in its basics tab, instead of targeting cues,
12:58
I'm going to ask the fade cue to target maps.  And when I select map, I then am presented
13:06
with a list of maps. I'm going to choose this  map. And now I get an objects tab in the fade
13:14
cue only. And all I can do here is move is the  is the portion of fade cues. No, the fade cue that
13:25
targets the map can do everything a fade cue can  do to an object, but nothing else because there
13:33
is no other parameter to adjust here. I can grab  object double A and I can send it around the room
13:50
perhaps slowly, continuously in  an oval by taking that cue,
13:59
making a start cue to restart it with a tiny delay.
14:06
Putting the two of those in a start first group
14:16
and rolling that. Oh, that's way too fast.
14:30
Let's make that
14:36
There we go. Yeah. Anyone got any T? Yeah.  Okay. This fade cue which moves this object
14:47
has no level controls because there is  no inherent level going on with the map
14:56
object. The map object lives on the map and  moves around and just does its own thing.
15:01
and individual cues can send their level to  it. Does that make sense? Some folks I think
15:10
um are likely to use map like I have a  colleague who prefers using map objects
15:16
because he likes the idea of an object.  Uh I don't want to put words in his mouth, but what it seems like he said is that he prefers  the idea of the object having permanence. Little
15:27
object permanence joke there for you. The object  having permanence in the space as though it is a
15:33
real object. He can predict its location rather  than individual cues objects which are ephemeral
15:39
which come and go. So this object loop could  keep going indefinitely forever and individual
15:46
cues could stop or start and join up or drop off  with the object as it spun around the room. Right?
15:58
The key uh detail to point out then is that if  you want to both move an a map object and make
16:07
a level adjustment pertinent to that map object,  you need more than one fade. One fade moves the
16:14
object. Other fades tell cues, hey, you take your  level out of that map object or up in that map
16:20
object or whatever because the level belongs to  the cue, not to the object. That make sense?
16:31
While we're here, it's worth pointing out that  the fade cue, which targets a map, has its own
16:37
icon type, just to give you again a  little clue. And while we're there,
Fading audio patch levels
16:46
cycling through target types has a  keyboard shortcut, which by default is option T for target. You cycle through cue,  patch, and map. When a fade cue targets a patch,
17:01
you can select an audio patch and then it has  a levels tab. This levels tab lets you automate
17:13
the patch routing levels here. So you can  fade the actual output matrix of a patch.
17:22
The main reason you might do this, I can imagine,  is to put uh some kind of control to give you some
17:28
control over the main output fader so you can duck  down things, right? Um our previously discussed
17:35
uh fire emergency. You could have you could  be prepared for a less serious emergency,
17:42
right? You could be prepared for um what if  you have a QLab workspace that runs lobby music
17:48
and you want the house manager to be able to duck  that music so that they can holler that the house
17:54
is open. You could make them a fade cue which  ducks down the main level of the patch so that
18:04
they can then duck that down and say, "All right,  folks. The house is open. Go on in." And then run the fade cue to bring the patch back up. That  way, all audio which passes through that patch,
18:13
regardless of when it starts or what level it's  set to, has been ducked because the main level of the patch has been ducked. I also want to  point out that this is a pretty easy space to
18:23
get yourself in trouble because you can duck  down the main level of the patch, not notice,
18:28
not remember, whatever, walk away, have a break,  come back, and then say, "All my cues are wrong."
18:35
and then program all your new cues really really  loud and then later realize what you've done and
18:40
have a lot of disentangling to do. Um, it's  not only troublemaking, so that's why we have
18:48
it. But I just wanted to point out that that's  a that's a possibility because this is a window that may not usually be open. So this main level  being out of place may not be visible to you.
19:01
When you do if you do fade the um main level of the  patch patch or any level of the patch,
19:16
it's drawn differently. The box that contains  the number is outlined in yellow and there's a
19:24
yellow bar inside the fader track if it's a  one of these controls up here that shows its
19:29
home level. Here's a fade cue with its own special  icon showing that it's fading settings a uh fading
19:39
a patch rather rather than a cue or a map. Any  control will that has been faded will display as
19:50
um with a yellow border and if it has faders  you'll see a line showing the home value and
19:56
the reset button will appear in the tab which  lets you reset that whole tab to its home
20:01
position. You can also use a reset cue targeting  either a patch or a map. When you run a reset cue,
20:13
it restores everything in uh everything that  it's targeting to its home saved level. Right?
Unsaved changes and live levels
20:25
Notice um this is something that maybe  um experienced macOS users recognize but
20:34
others may not notice. The traffic lights in  the upper left corner of all windows. Right?
20:40
This is the red one means close the window.  The yellow one means minimize the window. The green one means change the window size in  a series of complicated ways that Apple has
20:50
slowly changed over the years without  any systemic pattern design or logic.
20:58
The red button here we see the red button is drawn  just a flat red space. But if I make a change to
21:05
my workspace, basically any change that you can  undo, command Z, undo. Notice the red button has
21:12
a dark dot in the middle. The dark dot, this  will happen in in all well- behaved macOS
21:19
applications. The dark dot means a change has been  made that needs to be saved or not saved, but it's
21:27
your choice. Have you ever closed a window and the  computer says, "Do you want to save your changes?
21:34
The red dot, the dot in the red button is the  thing that lets you know that you will be asked, do you want to save your changes? If you command  Save, the dot goes away. It's a single bit in the
21:49
metadata of the file. If the bit is a value of  one, it means things have been changed. Ask the
21:55
user to save. If the bit is zero, it means  nothing has been changed. You do not need to
22:00
ask the user to save. I kid you not. The name  of that bit is the dirty bit. A workspace that
22:06
has been changed or any document that has been  changed is considered dirty. Saving it cleans it. And I think that the whole reason for that  metaphor is so that they can call it the dirty
22:15
bit because that sounds like fun to someone.  Um, and it made you all chuckle. So, you know,
22:21
I guess they're right. Um, so the reason that  I'm pointing all this out besides, you know,
22:27
esoterica can be fun, is um, when you make  a fade on a level in the workspace, notice
22:40
the workspace is not dirtied.  Changing a level by a fade cue
22:47
isn't a savable change. Right? If I quit  and restart QLab and reopen my workspace,
22:53
this level will not be - 29.5. It'll  be back at home where it belongs,
23:00
-12, which is what's saved. The home value is  saved in the workspace. The result of fades is not
23:07
is is not saved, is not permanent. It's a passing  change. Right? I'm just trying to as many times
23:14
as possible without being laborious re-emphasize  um save changes, home values, unsaved changes,
23:22
ephemeral values, what will go back when you press  reset, what won't go back when you press reset.
23:27
Yeah. Okay. So, map objects and fading. What's  your problem? No parameters are set to fade.
23:39
I found another bug, Chris. When you take a  fade cue and target a map and do some stuff and
23:48
then retarget that fade to something else and  then return, it thinks nothing's set to change
23:59
until you click in the map. Then it wakes up and  realizes you made changes uh in the objects tab.
24:11
24. Go to go to minute 24 and listen to  what Sam jabbers about. Okay, great. Yeah.
24:24
Yeah. So, I kind of blew past this, but  you were correct to draw me back in and not allow me to handwave. What I've done  here, because someone asked yesterday,
Looping fades
24:35
can fade cues loop? And they can't. But that  seems awfully helpful if they could. I made
24:41
a fade cue. It auto follows to a start cue which  has a tiny delay on it. That start cue restarts
24:48
the fade cue. And then I put them together in  a start first group. When I roll this group,
24:55
this fade cue will run for its whole  duration. Then it'll trip the start cue,
25:00
which will restart the fade. And this is a really  useful technique, right? Unless I do something,
25:09
this will run forever. And the question is, how  do you stop that fade? My recommended way to
25:15
stop this fade would be to use a stop cue targeting  the group. Then the group will be told to stop,
25:22
which means its children will be told to stop.  You could make a stop cue targeting the fade cue.
25:28
But if you were very unlucky and you ran that stop  cue during the one tenth of a second that the start
25:34
cue was going, it would have no action. Then the  start cue would go and then the fade would restart.
25:40
So I target the group which says everyone in  me, whoever you are, whatever you're doing, knock it off. Now that stop cue would not allow  the movement to slow to a halt. And to do that,
26:03
to do that, I'd make a fade cue targeting  the group. The fade cue would be relative.
26:15
The fade cue. No, this is not possible. It's not  possible because the fade cue would be targeting
26:22
the group. The group has no objects. The objects  belong to the map. The fade cue cannot target both
26:29
the group and the map. But you could make you  could make the fade cue target the map tell the map
26:41
relative fade of this object
26:49
to some location. No, I don't  really know how to do this. I don't know that there's a good way  to make it just coast to a hole.
26:59
Do you? Yeah.
27:06
Slow down. Wherever you are, slow down and stop. I  don't think there's a good method for that. Yeah.
27:21
on the start. Yeah. So,  because uh here we go. Okay.
27:30
Time is weird. And that's like true.  Time in computers is a its own other
27:40
layer of weird. Everything in a  computer happens on a schedule.
27:46
So you can tell the computer, please do  this thing as soon as possible or please do this thing a certain amount of time in the  future. I'm glossing over a lot of details.
28:01
It is um for reasons it is really  hard to know the exact instantaneous
28:14
atom of time at which moment a cue halts. We can  tell a cue to stop and you can hear it stop if it's
28:25
an audible cue or see it stop if it's a visible  cue. But there is after that a tiny fraction of time
28:31
down at the computer scale in which the cue  is still running after it seems to halt. Like
28:41
the same way a tape deck back in the day when you  hit stop it would stop but then the heads would
28:47
twist just a little bit more because they had  mass and momentum and so they would just twist
28:52
a tiny bit more. That's not at all what's going  on here but it's a useful metaphor. If you tell a
28:58
cue to start during that tiny window of time, it  considers itself still running and won't start.
29:08
Because cues that are running won't  restart. When you tell a cue to start,
29:15
if it's already running, it's like, I'm running.  What do you want from me? Right? The ostensible
29:22
first lesson of today is the triggers tab where  we talk about a way around that. So stand by for
29:28
more. But the short version is when this fade  gets to its very end conclusion, we give it a
29:37
little grace period to be absolutely certain that  it's truly and fully stopped before restarting it.
29:43
My colleague Ethan has devised a clever scheme  whereby um remember yesterday I was making fun
29:50
of D&B for me having to lie to the software to  make the speaker sound correct. Ethan created a
29:56
clever way where we lie to QLab about whether a cue  is running where QLab lies to itself and says well
30:02
if it's within this very narrow window at the very  end of the cue it's probably supposed to not be
30:08
running. So let's pretend it's not running.  And that is a little bit of a hack. But when
30:13
you really spend enough time with computers, you  learn that all solutions have some little hack in
30:20
them somewhere. Almost all. And so Ethan's devised  this scheme which we may put into play soon or we
30:28
have to we have to really bang on it to make sure  it doesn't do something unexpected or untoward. Um but for now it doesn't have to be a tenth of a  second. I bet I bet a hundredth of a second would
30:39
do. Um, but you do need to just give it that  little buffer to make really sure it's really
30:45
stopped. And I I feel Chris itching to chime in.  So, I will invite him to do so. I'm sorry. No,
30:53
no, no. You're getting you're getting my energy  right. Yeah. No. Um, this is this is annoying and I'm sorry about it. We when we were Yeah. No, it's  it's um when Ethan proposed a way to essentially
31:05
fix this, I was like, why did we let this sit like  this for so long? So, it's going to get it's going
31:10
to get fixed so that you don't have to add this  little extra cheat li time. Um, and and truly
31:16
the only reason I think that it wouldn't be right  away is we don't want to it's one of those things that's delicate enough that you want to be careful  about when you send it out into the world. So,
31:24
it could be as late as V6 that we change this uh  just to make sure we don't like mess anything up
31:29
for anybody in running shows. Um, but it will  it'll it'll this this little lie this tiny
31:35
little lie will go away. It is genuinely very true  about when you start getting down into the world
31:41
of clocks and QLab deals with lots of different  clocks in one show, it starts being very mind-bendy
31:48
and you have to think real hard about how time  works for different clocks who are all pretending
31:53
to tell you the same time and not uh and so it's  it's an interesting rabbit hole to go down. Um,
32:00
just going back to the C the previous question.  I think this question about fading a path sort
32:06
of slowly out is within this cluster of features  that I think we're excited to tackle for probably
32:12
version six of like speeding up and slowing down  a path and the rate changes on a path and looping
32:19
paths. And there's sort of a whole cluster of  things that now feel very obvious that you would want to do with with objects moving on pads that  it was just enough of another batch of work to go,
32:29
okay, this thing is very helpful. Let's get  it out into the world and then we'll do the next batch of work next. Yeah. A lot of what's  really great about QLab relies on the fact that
A discussion about clocks and synchronization
32:41
unlike most other media playback software, QLab  does not have one clock to rule them all. If you
32:47
have cues playing to an audio device, the audio  devices clock is in charge of the audio playback
32:55
for those cues. But if you have other cues playing  to another audio device, that audio devices clock
33:00
is in charge of the timing of the audio for those  cues. If you have a video playing to a screen that
33:09
has no audio related to it, the timing clock of  the screen drives the playback of that video cue.
33:16
And all three of those cues could be playing  simultaneously or groups of cues playing to all three of those devices simultaneously. And you'd  have those three clocks in charge of those three
33:25
sets of cues. Well, let's pretend for a moment  that those two audio devices and that screen are
33:31
all cheap as can be, have the crummiest clock chip  in the world. And so the clocks, the three clocks,
33:38
we play a six-hour cue in each of them. By we  by the time we get to the end of those six hours, they may be wildly off, right? Because the price  difference between the chip that keeps clock well
33:50
and the chip that keeps clock very well is like  a 100x difference in price. To get a clock that
33:58
is loses no more than a second or two in a day  is like 20 cents, 25 cents, not bought in bulk.
34:08
To get one that loses uh one no more less than  one tenth of a sec second is is like $20 or $30. Um,
34:18
so it's reasonable to understand that like for  almost all the time if you like you know some
34:23
cheap inexpensive... I don't mean cheap like flimsy  I mean inexpensive, I mean affordable, computer
34:28
monitor like no one cares about this kind of  timing thing over great distances so it makes
34:34
no sense to inflate the price dramatically to have  a super precise clock in it. Other software says,
34:42
"All right, pick the device in your system  that is going to be the clock the clock and
34:48
then all of your stuff will synchronize to that  clock." Which is great until you need to play
34:53
some audio out of this device, some audio about  that device. That device doesn't have any way to know about this devices's clock and you get skips  and pops on the audio coming out of that device.
35:03
So QLab's, one of QLab's big advantages is, you  know, just play stuff to places and the different
35:09
clocks will do what they do and everything will  sound and look nice, which is true until you
35:15
get to a place of needing some really detailed  exact synchronization between disparate devices
35:22
and then we have to do something complicated  to figure out how to make them all agree. And um I strongly stand by our design choice to  make the common thing which is just play stuff
35:33
many places easy and the uncommon thing which is  just play stuff many places and also have really
35:39
really really tight sync make that much more  difficult. Um I think the alternative would be to
35:45
put shackles on folks who need to do an easy thing  easily. Uh and I would rather not do that. When we
35:54
get pretty soon to the triggers tab and talk about  that and when Sam talks about the wall trigger,
36:00
I'll I'll jump in with a little story and remember  this remember this little moment about clocks
36:05
being weird and shifting time and I'll tell you a  story about wall clock triggers when we get there.
36:14
Uh, on which topic? Triggers. Oh, look at that. So  that was the, like, object audio coda, end of object
The Triggers tab - hotkeys, MIDI, wall clock, timecode
36:26
audio lesson which if I had really been thinking  about it uh I would have finished yesterday with.
36:33
Now I will talk about the triggers tab which um  I've been putting off all day yesterday because it's great but also it's sort of a little bit  farther down the rabbit hole. It's where I hope
36:43
you feel you are now. Um the triggers tab which  exists for every type of cue in QLab is a powerful
36:52
tool um for subverting the expectation that the  show just happens with cues in order linearly one
37:00
at a time or maybe a few at a time, the same order  every night. The triggers tab provides a way to do
37:10
other things. And so we're going to talk about  the two sides of the triggers tab. It appears
37:16
like this. It's got a divider more or less in the  middle. Not really middle, but you know, it's got a divider towards the middle. We're going to talk  about the left side of the triggers tab first. The
37:25
right side of the triggers tab second. The left  side is uh can can all fall under the heading
37:33
ways to get the cue started other than the go  button. Okay. The first type of trigger we're
37:42
going to discuss is a hotkey trigger. A hotkey  is a key on the keyboard, the computer keyboard.
37:52
And it's it's hot because it's ready to do  something at any time. So, I've assigned
37:59
in the triggers tab the number one to this  cue, and nothing has happened because of it.
38:11
That's odd. I had to un-assign and reassign.
38:18
It's hard to say what's going on. When you  press this one on this keyboard, no matter what,
38:25
no matter where you are in QLab, no matter what's  going on, no matter where the play head is. I'm off here in another cue list talking about all  kinds of stuff, hitting go go go go. And then
38:34
someone's like, "Show me that tigger quick."  and I hit one, it appears. So, if you need,
38:41
if you're doing, you know, a oddball piece  of theater and the director says to you,
38:47
I want at any time you to be able to uh ring a  little bell. You can make somewhere in some cue
38:55
list an audio cue with a little bell, give it a  hotkey, and whenever you press the key on your keyboard, that bell will ring. It doesn't move the  playhead. It doesn't interact with the playhead.
39:04
that has nothing to do with anything other than  itself. Okay, so that's the hotkey trigger. Um,
39:12
I should point out that you can add  modifiers. So it could be shift 1,
39:18
it could be control 1 or command 1. But  let me encourage you to avoid using command
39:29
plus anything in your hotkeys because command...m  the hierarchy of modifier keys in macOS for
39:38
keyboard shortcuts is, command something is the  most common hotkey. Command plus option something
39:45
is the most common, the second most common.  Command plus shift is the third most common.
39:53
Every hotkey that starts with a control key, control n,  control o... that's really common in Unix. And so
40:00
when Apple released macOS uh one um sorry macOS  10.1 they decided or 10.0 really they decided,
40:10
we're going to let control plus something just  be the Unix hotkeys that Unix people are used to
40:17
which means most of the time control plus anything  when you're using QLab is available to you. So if
40:24
you want a hotkey that is more complicated than a  single key press, right? Because if I just hit one
40:31
by accident in the middle of my show and Tigger  appears, that could be awkward. Yesterday. Yeah,
40:42
I did that on purpose. Um, I was hunting for  a button and I did not do that on purpose. I'm
40:49
trying to be witty. Um, so you want to maybe make  it a little harder. Okay. Well, let's make it uh
40:56
a two key thing. I have to have control and one.  So, control one is harder to hit by accident. So
41:06
that's why there's a reason that's a reason to use  a modifier key. Even shift one is harder to hit
41:11
by accident, right? So these are just things to  think about and consider. Um it's worth pointing
41:20
out that on a extended keyboard the number keys  are technically different key different numbers
41:26
than the key than numbers over here. So the the  number pad on the right side is a separate one
41:35
and one are not the same one. And if you are using  a keyboard that is not the standard US layout, you
41:45
are entering a world of confusion. We have tried  our best. Apple has tried I assume their best. Um,
41:54
but if you have a different keyboard layout, it  can be very challenging to know like if I say, oh,
42:01
left and right bracket is pause and unpause,  right? I said that yesterday. To start with, Brits don't use the word bracket to mean  that symbol. Let's just start with that.
42:11
The the curly ones that we call braces or  curly brackets. That's a bracket, I think, to a Brit. Or maybe a parenthesis or brackets to  a Brit. Anyway, it doesn't matter. Braces are what
42:22
hold up your trousers in Great Britain. But to  us, braces are the curly things that surround
42:28
numbers. But that's even entirely separate from  the fact that these two buttons on a UK keyboard
42:36
are not these symbols. So what are you supposed  to do in Great Britain to pause and unpause? Are
42:42
you supposed to press the buttons that are to the  right of the letter P, or are you supposed to go find wherever the square brackets are and press  those buttons? And I don't actually immediately
42:50
know how to answer that question because every  time I confidently say you do this, turns out it's
42:55
something else. Um, and I once read a long very  dry paper on why this is actually a very difficult
43:02
problem to solve. I'm not going to subject you to  it. But the short answer is if you're listening to this uh or watching this video later and  you see me refer to any keyboard shortcut,
43:12
I'm using a US keyboard layout. And if you're  using a different keyboard layout, I encourage you
43:18
to experiment in a low risk scenario to find where  the key really is on your keyboard. Um, and then
43:27
tell me about it. And if you're using especially  a French keyboard layout, I wish you luck because
43:34
I have found that French keyboard layout and QLab  are as far apart from comfortable as I have gotten
43:41
um, when I was doing a show in France. A user  on the chat says in Germany we don't even have
43:47
the brackets printed on Apple keyboards at all.  Sure. I guess Germans are bracket averse is the
43:54
Apple's assumption. I wouldn't dare to guess.  Yeah. Well, I'm sure I mean I'm sure Apple's
44:00
wrong about that. It seems like ordering of  things and putting things in sections feels very
44:10
seems like it'd be right up their alley. Um  the uh the Grand MA lighting consoles made by
44:17
a German company. It is a very logical, rational,  sophisticated piece of machinery. Um all right,
44:24
moving right along before I get myself in  terrible hot water. The next kind of trigger to talk about is the MIDI trigger. MIDI, which  stands for musical instrument digital interface,
44:36
is a very very old standard. Um, it was devised  by Yamaha and Roland and a couple of other
44:44
manufacturers of electronic music making equipment  in the 60s um um so that devices that were made
44:54
by different companies could interoperate without  the companies having to every single time saying, "Hey, I'm selling a new synthesizer starting  on Thursday. These are the signals that
45:03
will make it do stuff. If you want to  make a controller that talks to it or no, we'll just support MIDI which will be a standard  that we all agree on. MIDI was engineered to be
45:12
um inexpensive to implement, reliable and  predictable and it has proven to be exactly
45:18
that for decades and decades. Um it's not the most  flexible in the world, but it turns out that it is
45:24
sufficiently flexible for most cases. So QLab has  good strong MIDI support. In the triggers tab,
45:32
you can check the little box and accept a MIDI  message of any of these types. Note on, note off,
45:38
program change, control change, key pressure,  channel pressure. You might ask, how did we select
45:43
those six messages as the six messages to allow  for MIDI triggers? And the answer is, we guessed,
45:50
and we figured that if anyone wanted to use a  different type of message, they would write to us and ask. And no one ever has. But if you want  to use a different type of message, please let us
46:00
know. It is easy to add. We would do it probably.  Or you can just click capture and then press a
46:12
key on your MIDI device and it will capture the  incoming MIDI message. The note number is captured
46:19
here. If you've got a note on message, the note  velocity is captured there. If you're using something like a control change message, then  that's the control number and that's the value.
46:30
The velocity message has some tricks. It  can use greater than or less than. So if
46:36
you have a velocity sensitive keyboard and you  type greater than 50, if you just tap the key,
46:44
it won't trigger. But if you hit it harder than  50, it will trigger. It can also do less than.
46:52
So you could have two messages, I'm sorry, two  cues that both accept a trigger. One captures
46:58
any hits of the key with a velocity of less than  50, the other with a velocity of greater than 50.
47:04
And then you would discover how often you manage  to hit the key at exactly velocity 50 and get no
47:11
cues at all. Or you can also do velocity any. I  want to warn you a little bit about this because
47:20
the correct behavior of a MIDI device is to send  a note on with a velocity when you press the key
47:28
and then ideally a note off with a matching  velocity when you release the key. But it is
47:36
an accepted standard behavior though it is not I  think technically correct. It is widely accepted
47:42
that a note on with velocity zero is also okay  to send when you let go of the button. And indeed
47:48
that's what this device does. So note on velocity  something when you press note on velocity zero
47:55
when you release. So that means that when you use  velocity any you will get two triggers. So if the
48:01
cue is very brief and you hold the key down long  enough you could get bing bing if you use velocity
48:07
any. So for that reason when I use a velocity  sensitive keyboard I usually type greater than
48:14
zero as my velocity message so that you can hit  the key as hard as you like or as softly as you
48:20
like you'll get one message but when you let  go of the key the velocity zero message will not be received as a trigger. Does that make  sense? Yeah. So just to clarify that velocity
48:29
parameter is I will trigger when I receive this  exact velocity. So if you had it set to 127,
48:37
that would only trigger what you slam on that on  that key. Anything less than absolute max would
48:42
trigger. That's correct. This MIDI device  is not velocity sensitive. So no matter how
48:48
hard I press the key, well, there's only two  possibilities, right? One is I hit the key and
48:53
it produces a velocity of 127. One is I hit the  key much too hard and I break the controller.
49:01
Um, so yeah, velocity 127 exactly is only useful when you don't have a velocity  sensitive device as I do here.
49:10
The wall clock trigger
49:16
should explain the little ping that you heard  while I was in the middle of talking about something else yesterday at 6 minutes to 4 p.m.  The wall clock trigger triggers a cue at a
49:27
specific time of day. So, it's 9:46 a.m. right  now. I'm going to go to 9:47 and 0 a.m. And at
49:40
some point, awkward. I was going to say at some  point within the next sentence, 9:47 rolls around
49:47
and we hear that ping. Right. This time of day is  hours, minutes, seconds, a.m. or p.m. Or you can
49:54
use a 24-hour clock. And then this button every  day lets you choose days of the week to turn on or
50:00
off for this trigger. So you can have a cue that  triggers at 9:47 a.m. only on Monday, Wednesday, Friday, or whatever you like. I've used wall clock  triggers um for pre-show announcements when I'm on
50:13
I beg your pardon when I'm when I was an operator  on a show where I was required to be in the booth
50:21
uh at half hour to trigger the cue that plays  an announcement in the lobby welcoming people into the audience. Simultaneously I was needed  backstage to put wireless microphones on the
50:32
children in the show who were not being entrusted  to mic themselves. Um, and while I sort of stamped
50:40
my feet about needing an A2 on the show, uh,  my producer, uh, laughed in my face. And so
50:47
I programmed the pre-show announcement with wall  clock triggers. Right. So at half hour every day,
50:53
the pre-show announcement ran by itself while I  was backstage putting the mic on mics on the on
50:58
the children. But of course on Thursday,  our show is a half an hour earlier. So I untick the box for Thursday on the main pre-  announcement. Then made a copy of that cue,
51:08
gave it a half an hour earlier trigger time and  triggered tick the box only for Thursday. But then of course on Sunday we also had a matinee. So I  made another copy blah blah blah blah blah. There
51:17
are folks who use QLab um to play ambient music in  a theme park. I never remember what theme park,
51:23
but um they have just huge numbers of wall  clock cues in their show because this time
51:31
of day is when the something pavilion opens and  that time of day is when the what do you call it thing happens and that time of day is when  we're going to be closing soon and you should
51:39
really make your way towards the exit, stuff  like that. So they have just piles and piles of wall clock triggers and it works beautifully for  them. Um, one thing that is worth noting is that
51:51
uh there is a vagary in the way that the Mac  OS reports time to software. To my understanding
52:00
uh it is not able to be clear when you will  receive um if you a second has a duration, right?
52:11
Is the is the 947 and OO going to trigger right at  the beginning of 9477 and 0 seconds or is it going
52:19
to trigger just before 947 and 1 second? And the  answer is that the way that macOS reports time
52:24
to us, it's going to happen sometime within that  second. So there's a small amount of slop which
52:32
you need to accept if you're going to use wall  clock triggers. Additionally, uh, pursuant to
52:38
my earlier conversation about clock chips, the  internal clock on a Mac is pretty good, but if
52:43
you don't let the Mac connect to the internet,  the clock will drift by as many as several
52:49
seconds in a day. So, if you're using wall clock  triggers and you're using a Mac that is offline,
52:56
you're going to want to routinely check the time,  I'd say once every couple of days, just to make
53:02
sure that it's still accurate. And that amount of  drift is sort of normal. If the clock on your Mac
53:08
is routinely resetting itself dramatically, more  than a few seconds a day, that means that there's
53:14
a physical problem going on, and you should  get that Mac looked at. If the Mac is online,
53:20
it will automatically set its time using a time  server, and you don't have to worry about it.
53:26
And you had something to say about time. Yeah,  you actually covered it pretty well. So, so I'll
53:31
be faster than I would otherwise would have been.  But, uh, so this the wall clock trigger here, I'll
53:37
this is enough of a story that'll come up. Um, the  wall clock trigger was introduced in version one.
53:42
The reason it was introduced is kind of fun. I got  an email from someone uh uh in Germany as it turns
53:48
out the theme for the morning uh who was building  a show and the show was being hosted inside an
53:55
under inside a submarine bunker which from World  War II. And so the rooms that people were going
54:03
to be in had walls between them and those walls  were six feet of concrete. So they had different
54:10
uh events happening in different rooms that they  needed to roughly coordinate and there was no way to connect those computers together in any  way through six feet of concrete. So they said,
54:19
"Well, can I trigger it off the the clock uh and  we can get basic coordination?" So that's why wall
54:24
collect triggers were added. But I didn't know  at that time everything that Sam just taught you about the fact that clocks drift as much as they  do. Uh I and and back then I think it probably
54:35
was even a little bit worse. So, I would uh set  a clock when I was testing and it would go off
54:41
at the time I expected. And I thought, great.  I sent it out into the world. It worked for this submarine bunker. Huzzah! The feature is  done. We move on with our lives. And I started
54:49
getting messages back from people who are using  it in different circumstances saying, "It's not triggering when you when I set it to trigger. It's  four minutes late. It's a different time of day
54:59
entirely." And and I was very worried and confused  because it I it was working just fine for me.
55:04
So this these clocks drift different amounts for  different computers. So what is actually happening
55:10
in there now is that QLab is actually scheduling  it once every minute and it checks every single
55:17
minute for each wall clock trigger. Is it going to  happen within the next minute? If so, the clock is
55:22
not going to drift that much within a minute.  Otherwise, if I'm online, I'm going to ask, "What the heck time is it?" and recalibrate myself  once a minute until this thing happens. Because
55:32
otherwise, as Sam said, these clocks can drift.  a a remarkable a remarkably surprising amount and
55:38
differently depending on the computer because  the electronics in there just are physically behaving differently. So this this gets back to  this strange clocks are weird. Time is strange.
55:49
Don't make big assumptions without checking them.  And I want to like draw a distinction. Clocks are
55:55
weird and time is strange. Both of those things  are true and they're not actually related. Like
56:01
time is strange just time. I don't mean like  how we keep track of time. Like it's strange
56:07
that time goes differently when you're moving fast  and when you're moving slow. That's strange. But
56:13
it's also strange that keeping track of time is a  mechanical challenge. Um older Macs had a little
56:21
rechargeable battery in them that would recharge  routinely when the Mac was connected to power
56:27
and switched on. That would keep the clock running  when the Mac was switched off. Newer Macs use some
56:34
other method. I think that is not like literally  a battery in a little battery holder on the PCB.
56:41
I think it's a different sort of charge holding  device. Maybe a capacitor or maybe it's a battery, but it's soldered on or I'm not really sure. But  also what's part of what's different is that it is
56:53
no longer our recommendation necessarily that your  Mac is kept offline when you're using QLab. Um,
57:00
keeping your Mac connected to the internet all the  time for a show computer used to be considered a
57:06
definite no no. And I just don't feel that way  anymore. Instead, I'm let your Mac be online. I
57:12
don't care. Just make sure you don't have any  ill-behaved software on your computer. And if you're not really sure what that means, if it's  made by Adobe or Google, and then you're okay. Um,
57:22
and by which I mean without being snippy, Adobe's  um, background update checking software is,
57:29
shall we say, assertive. Um, Google's background  checking software is both assertive and needy and
57:37
verbose. So, if Google's uh auto-updater can't get  to the internet, it tries again in 5 seconds and
57:45
then again in 5 seconds. And then every time it  doesn't work, it logs a big long message stamping its feet saying, "I tried to update Chrome and  I could not." And it was exactly this time and
57:54
I don't like it at all. And then it would do  that every 5 seconds and then every one second. And so keep Chrome off your computer for a lot of  reasons in my opinion, mostly because it sucks
58:05
your battery dry, but also because it's up auto  updater is a real complainer. Or use Chrome and
58:11
just ask it not to autoupdate, which is also fine.  Adobe's auto-updater just very very aggressive,
58:18
always checking. Would you like to install Bridge?  Do you know what bridge is? What is Bridge? What's a bridge? I'm just making photographs. Leave me  alone with your Bridge. But uh Bridge needs to
58:26
update. Like on and on and on and on. Nowadays,  most internet connections are pretty fast. Most
58:33
software, even complain-y software, just sort  of says, "Do I need an update?" "No, I don't." Great. Moving on. And um QLab's ability to sort of  do what it does. Again, we've been talking uh many
58:44
times about how fast these computers are getting.  QLab's ability to get what it needs done with the
58:50
available resources given to it by a very powerful  Mac stays the same as the Mac gets faster. So more
58:59
of those background am I ready to update or do I  need to do something messages more of those things
59:05
can be tolerated because there's more processing  power available and because the average speed of internet connections is up so it's just not such  a big deal anymore. Um, also Apple's been very
59:17
aggressive about security practices and most of  the time that's annoying because you get asked if you're sure that you want to allow this microphone  to be do are you sure you want to allow your
59:27
recording a audio recording software to use the  microphone. Well, it's kind of why I bought it, pal. Um, but that those security practices  do have an upside. And the upside is it's
59:37
much less likely that something is going to just  bomb your show simply because your Mac is online.
59:43
Okay, the next type of trigger is a timecode  trigger. Time code is a technology that was
59:49
invented for keeping film cameras and audio  recorders synchronized on a film set so that
59:55
the editing process would be easier later. And  then um because theme parks tended to be opened
1:00:05
by film people like Universal Studios and Disney  World and so forth, um it was the film people who
1:00:13
had to figure out how do I get this airplane model  to go down this ramp, fly towards the audience,
1:00:22
land in this pool of water at the exact same  time that the actor is exiting here and a
1:00:29
sound effect is happening and the lights are  focusing on that and this is the water world uh installation at Universal Studios I believe and  how do I have all these things happen in perfect
1:00:40
sync and do it six times a day every day forever  and they figured timecode let's use timecode we
1:00:45
know about timecode timecode works perfectly on  our film sets it'll work perfectly here and the truth is that timecode is a really useful tool  for synchronizing events and it's used commonly
1:00:56
in live events and it is my position that  it is most of the time okay and seldom ideal. It's
1:01:04
really good for keeping your tape recorder and  your film camera in sync, but most live events
1:01:10
aren't on a rigid timeline. Most live events have  some flex or want to have some flex. I did a show
1:01:18
for a cruise ship and the standard behavior in  cruise ships is the whole show is as they say on
1:01:25
rails. So it's a half an hour show. You press  go and then 30 minutes later curtain call and
1:01:31
that's it. And timecode drives the whole thing.  But I was doing a show that I didn't know this
1:01:38
at the time. Apparently this is uncommon that the  script for the show was genuinely funny. And as a
1:01:44
consequence we had laughs which we wanted to hold  for. And so because I'm a QLab person and I was I
1:01:51
was the new guy in the group, I was like, why  don't we just freeze timecode during the book scenes and then pick it back up for the next  song? And everyone was like, you are a crazy
1:02:01
person. How how will that work? And I was like,  why don't you all just let me try it? And we did that. We ran timecode for the song. Then we  held timecode. There were no light cues. There
1:02:11
was no video changes. They did the book scene.  People laughed. Sometimes it was long. Sometimes
1:02:17
it was short. And then as soon as the laugh was  done and the guy turned to start the next song,
1:02:23
we hit go again. Time code picked up again.  Everything synced up and we had more cues for the
1:02:28
next song. And it worked really well. It worked.  So in my opinion, timecode in bursts with gaps
1:02:36
is kind of the best of both worlds. I'll leave the  further discussion to people's choice whether they
1:02:43
want to talk about it or not. But in in summary,  QLab both can receive and transmit timecode in
1:02:51
two forms. We accept LTC, linear timecode, often  called SMPTE by film people. And we also accept
1:02:59
and transmit MIDI timecode, also MTC, which  is also... like, calling LTC SMPTE is like um
1:03:09
it's like calling uh my MacBook Pro "Apple." Like,  Apple is the company, the MacBook Pro is the model,
1:03:17
SMPTE is the organization, the society of motion  picture technicians and engineers, that devised
1:03:23
and sort of maintains the standard for timecode.  So LTC is the timecode. SMPTE is the governing body
1:03:29
that is in charge of timecode. So it's not false  that it's simp. But it's also not accurate because
1:03:35
also like some guy who works at SMPTE is also simp.  So is this timecode Steve? I don't know. Um MIDI
1:03:43
timecode and linear timecode are more or less  equal. Um MIDI timecode is inferior for a lot
1:03:49
of reasons. The first one is that the electrical  distribution of MIDI signals is more challenging
1:03:56
than the distribution of audio signals. The second  reason is that um many MIDI interfaces use a
1:04:04
buffer that is too small to fully capture a frame  of MIDI timecode. So um some perfectly functional
1:04:14
MIDI interfaces for all other purposes will freeze  up when timecode comes or goes. So then the third
1:04:22
reason that MIDI timecode is inferior is that um  it's a format referred to as a quarter frame format
1:04:28
which means um basically you get a frame of time  code that says we're here and then you get three
1:04:34
messages that are like two three four and then  we're here you get a full frame that tells you
1:04:40
everything about what time you're at and then you  get three more messages they're like 2 3 4. You know, if someone conducts and they count 1 2 3 4,  2 2 3 4, 3 2 3 4, but if you're not paying attention
1:04:54
and you only listen when they're going 2 3 4, you  might say, "What measure are we on?" Like 47 2 3
1:05:02
oh, we're on 47. Great. Good. MIDI time code is like  that. So if you happen to start listening during
1:05:07
the 2 3 4, you're lost for almost a second until you  get the next big frame. So that's that's the third
1:05:15
reason that MIDI timecode is inferior. That said,  people use it. So whatever. To use a timecode
1:05:24
trigger for QLab, you first have to go to the cue  list that the cue you wish to trigger is within
1:05:33
and enable incoming timecode for the whole list.  This is like a big the big Igor switch to turn on
1:05:42
for incoming timecode for the cue list. Once you  turn on timecode incoming for the cue list, you
1:05:49
have to make a bunch of choices. I'm going to hold  off on describing these choices until at least one
1:05:57
person either in the chat or in the room asks me  to go into them in detail. Sometimes no one wants
1:06:03
it and it's just a waste of everyone's energy. So  for now I will simply say does the list listen for
1:06:10
MTC in which case what MIDI device do I listen  to or does it listen to LTC in which case which
1:06:17
audio device do I listen to and which channel  on that audio device is receiving the signal and
1:06:24
once timecode is turned on forget about all the  rest of the stuff for now blah blah blah you can then go to an individual cue within that cue list  enable a timecode trigger enter a timecode or
1:06:36
click capture to stamp an incoming frame of time  code and say at that moment is when I want this
1:06:42
cue to trigger and then when that frame of time  code comes in the cue will start. Questions?
1:06:51
I will give one cautionary tale about timecode  which is these numbers right hours, minutes,
1:06:58
seconds, frames or reals, minutes, seconds,  frames, doesn't matter. Uh if you don't start at
1:07:08
hour one and instead start at hour zero, sometimes  weird stuff happens with older equipment.
1:07:15
That's the shortest version of that warning  I can give. So that's the end. Again,
1:07:21
we'll talk more if anyone wants to talk more.  Okay, that is the conclusion of the left side
1:07:26
of the timecode tab. That's four ways to get a  cue to start that isn't putting the playhead
1:07:32
on that cue and hitting go. All of them happen  at any time when the workspace is open. None of
1:07:39
them move the playhead or have any effect on  the playhead. None of them care which cue list you're looking at or are active. So all of them  can be considered just sort of hot at any time,
1:07:50
ready to rock. Does that make sense? Great.  The right side of the timecode tab is three
The Triggers tab - fade and stop others, duck & boost, second trigger actions
1:07:59
categories of things ow that pertain to  behavior of the cue while it's running.
1:08:12
or when it starts. The first is fade and stop. You  can set a cue to fade and stop other cues when it
1:08:28
starts. So this cue can be told when I go, you all  stop. It can fade and stop cues at one of three
1:08:39
levels of cue of QLab's hierarchy. It can fade and  stop its peers, which are all the cues that are
1:08:47
at the same hierarchical sorting level as that cue  in the same group. Or it can fade and stop list
1:08:57
all the cues in the same cue list, or it can fade  and stop all the cues in the same workspace.
1:09:05
We're going to do peers, which means that these  cues inside this group are all going to be each
1:09:12
other's peers. But this is not a peer because it's  outside the group. If I took these two cues and
1:09:18
put them in a group, that cue, that cue, and that cue,  and that cue are peers, but these two are not peers
1:09:25
of these two, right? Because they're in another  layer. These two are peers of each other. These
1:09:31
two are peers of each other. Yeah. Okay, great.  When you have a cue set to fade and stop peers,
1:09:42
you can also give it a time for the fading to  take place. So, it's kind of like a special kind of panic. And when you fade and stop peers,  one cue goes, the next cue that goes fades and stops
1:09:55
the first, then the next fades and stops the  next, and the next fades and stops the other.
1:10:00
Fade and stop peers is your friend when you're  making slideshows. It is your friend. Yeah.
1:10:12
The next option is duck or boost  others. So, here's a piece of music.
1:10:22
This music is playing at whatever  level I programmed. This next piece of um audio has duck audio checked. It's setting  to set to duck by minus12 over time 1.
1:10:36
When I hit go on this cue, all the other cues in the  same list will have their level ducked by 12 dB
1:10:44
over a 1 second fade. And then when this cue  ends, the level will be restored. So I hit go.
1:10:53
The pilot comes on. The music's ducked down.
1:11:00
And when the cue ends, the level restores.
1:11:06
It needn't be an audio cue that causes  the ducking, right? So, we could have our
1:11:12
pre-show music playing and then I could have a  slide that plays and when the slide comes up, the music ducks. If you put a positive level in  there instead of a negative level, it will boost
1:11:24
level instead of duck. I'm not really sure why  you'd want that, but we can do it. If you come
1:11:33
up with a good use of boosting audio while the  cue is playing, I would love to hear about it.
1:11:42
The last option on the right has is called  if running a second trigger dot dot dot. So
1:11:51
the default behavior of a cue when it is running  if it is told to run again is to ignore that
1:11:57
instruction. Right? I'm already running. Leave me  alone. But you can ask a cue to behave differently
1:12:06
than that. And I'm using hotkeys two through seven  uh on this on my keyboard to demonstrate this.
1:12:14
Hotkey 2 is for this cue which is set to if running  second trigger panics. So this cue is running. If it
1:12:24
gets another signal to go, it panics itself. Now  that's true no matter how it's told to go. So,
1:12:32
I use the go button. Now, I'm going to use the go  button again. Now, I'm going to use the go button,
1:12:39
but now use hotkey. Right? This cue, if it  receives the signal to start, no matter how
1:12:47
while it is already running, it panics. This  cue is set if running a second trigger stops.
1:12:57
And the reason there's reverb on this is because  I want to explain the difference between a stop.
1:13:06
I caused it to stop and  the reverb continued to go.
1:13:12
And you see in the uh status column there's a  little slope-y line that's fading out. The reverb
1:13:21
is doing its thing. This cue is set to hard stop,  not just stop. Same reverb, but when I give it
1:13:32
its second trigger, it stops dead and the reverb  stops dead. So hard stop means stop and also stop
1:13:38
your effects or whatever else is going on. Really,  really stop. Whereas just stop allows the reverb
1:13:45
to ring out. And panic fades out and stops. Hotkey  5 to me is the most fun. Hard stop and restart.
1:14:00
This is where we get into sampler territory.  Right? When you re when you trigger a cue with
1:14:08
hard stop and restart while it is running, it just  stops and restarts. So loop of object map fading.
1:14:19
If I set this cue to second trigger hard stops  and restarts, then I don't need that pre-we,
1:14:30
right? Because even if the cue is still running, when the start cue tells it to go, it  will hard stop and restart itself.
1:14:44
But my habit of the one of  the of the small pre-weight is ingrained from before we had the  hard stop and restart trigger option.
1:14:55
Um, this next one I'm going to use a MIDI um,  message to demonstrate because this next one is
1:15:08
called um, this next one has to do with this  checkbox below which is a second trigger on
1:15:13
release hotkey MIDI note. So when I press this  hotkey, this MIDI message, I'm sending MIDI note
1:15:23
9 velocity 127 to start this cue. And I have if  running second trigger set to panic. And I have
1:15:32
this checkbox checked which will listen for the  release of the MIDI message which is a velocity
1:15:39
zero. QLab knows about the velocity 127, velocity  zero pair or the velocity something and velocity
1:15:46
zero pair. And so a a MIDI trigger will be listen  will start the cue or and then listening for the
1:15:56
zero velocity release will panic the cue or  do the second trigger action. It also works on
1:16:02
the keyboard. I'm now holding down the number six  on the keyboard. And when I let go of six, that's
1:16:10
because that checkbox is checked, that will also  work. It also works in carts, which we haven't
1:16:17
talked about yet. So, there's this inevitable  thing where you have to teach something before you teach something else. And we'll get to carts.  Yeah. To reiterate, to reiterate, go back a little
1:16:27
bit. So the uh any cues with a trigger will still  go when the if the playhead lands on it though
1:16:33
when you hit go, right? Is that correct? Unless  it's already running. Unless it's already. So then
1:16:39
would you say this if you have a bunch of cues  that you really only want to activate triggers, you put them in like a separate list or something.  You're saying you want cues that will never be
1:16:48
triggered by the go button, right? Yeah. I always  put those in a second list so that there's no possibility of the operator accidentally running  them. Sometimes I have all my show cues here and
1:16:57
I have like several memo cues and then below that  I have a bunch of stuff so that only if they got to the end of the show and then hit go eight more  times could they get to those cues. That's just,
1:17:07
you know, to prevent me from flipping back and  forth between different pages, but usually I put them in a separate list. I worked on a show.  I was the associate on a show called Kung Fu,
1:17:16
which is about um was about Bruce Lee. And the  finale of act one was uh filming an episode of
1:17:24
the Green Hornet, which is a super fun  scene. And um while we were rehearsing,
1:17:30
we didn't have the fight choreo set, so we set up  our operator with a MIDI keyboard triggering a a
1:17:37
playlist full not a playlist, a cue list full of  punches and kicks and things. And so he could just watch Bruce and every time he did something  he played the piano and it absolutely, you know,
1:17:48
absolutely worked beautifully. Um, and that  was all in a separate cue list from his cue list of regular show cues so that he didn't have to worry  about where the playhead was or what was what.
1:18:02
The next option for the second trigger is uh a second trigger devamps. So here I have  a cue with a looping first slice, infinitely
1:18:13
looping first slice. When this cue is triggered  again, [Music] it devamps and exits its loop.
1:18:26
It's another useful tool, another  way to get out of a vamp, right? I
1:18:31
went to the triggers tab and I chose  if running a second trigger dev amps.
1:18:41
Next, here is a um there are two playlist  only options for second triggers. Um and
1:18:51
what they do is um make use of a uh quality  of playlist groups which is that when playlist
1:19:02
groups contain a cue that has an unknown or  infinite duration, the playlist can't advance,
1:19:11
right? Because this cue has no time. This cue is  just going to be up until it until we stop it.
1:19:20
So, I've set hotkey 8 to trigger the playlist  and I've set the playlist to if running a second
1:19:31
trigger plays next. So now every time  I hit hotkey 8, I get the next ticker.
1:19:46
Yep. I can also set it to play previous.  So, hotkey 9 does playing the previous. I'm
1:19:55
not really sure what that's good for,  but it was difficult for us to imagine
1:20:04
uh all the scenarios. So, we figured let's just  let it be and we'll have that option in there and
1:20:10
people might use it. I'm sorry. Slideshow maybe  if you want uh the previous one. Yeah, I guess
1:20:20
if the slideshow does automatically advance, but  I want to be able to jump back one. I could use
1:20:26
that. I don't really know. I just I can't think  of a design scenario where that would actually be a choice I want to make. But um anyway, that's  the triggers tab. Things to make the cue go,
1:20:42
things to tell you what happens when the cue  is going. It's a little bit of a mishmash,
1:20:48
but a lot of powerful stuff in here. And um  I want to call your attention once more to
The Workspace Status Window - Triggers
1:20:54
the workspace uh status window, which we looked  at briefly when we were talking about warnings.
1:21:01
The triggers tab of the workspace status  window lists all triggers, hotkeys,
1:21:09
timecode, MIDI, or workspace-wide messages, uh,  workspace wide keyboard shortcuts, excuse me,
1:21:18
that are set for the whole workspace. So,  if you set up a hotkey trigger, for example,
1:21:24
and when you hit it, two different sounds play  and that was not your plan, you can go to the
1:21:30
triggers tab of the workspace status window and  find your trigger here, your hotkey, and say,
1:21:36
"Oh, look, I have two different cues set to  hotkey 8. Now, I know that. Let me go fix that."
1:21:47
You can get to the workspace status window by  clicking this uh emergency icon if it exists.
1:21:53
But you can also go to the window menu and  choose workspace status. And the triggers
1:21:59
tab can be sorted by different columns.  So you can sort alphabetically by target, alphabetically by trigger,  or alphabetically by type.
1:22:08
And that's the triggers tab.  Yeah. Absolutely. Any cue,
1:22:16
all of what we just talked about  can works for any cue in QLab.
1:22:24
All righty.
Break
1:22:33
It's just slightly earlier than I  would naturally take a restroom break, but the next topic is not easily interrupted.  So I think let's take eight minutes and come
1:22:44
back and resume with MIDI MSC time  code and uh show control. Thank you.
1:22:56
I'm going to turn my microphone off.
1:33:12
All right, folks. How you all doing?
MIDI, MSC, MTC, LTC, OSC
1:33:18
It's time to talk about alphabet soup. Um so um  at the beginning of yesterday I described QLab as
1:33:30
being media playback and show control for live  events. Um my friend John Huntington who wrote
1:33:36
the book on show control which I believe is  entitled show control networks for theaters
1:33:41
um which is a fantastic book and I highly  recommend it. He defined show control as anytime
1:33:48
devices belonging to one department communicate  with devices belonging to another department. And
1:33:55
um I'm sure I'm misquoting him, but I'm  paraphrasing. Um and that works well
1:34:01
enough for me, more than well enough in fact. Um  show control is uh has become so prevalent that
1:34:08
I find it on in some form on almost every show  I do. And it's as little uh a thing as listen
1:34:15
for this one cue we really just want lights and  sound to synchronize just right. So can lights please send a MIDI message to sound to trip that  doorbell when lights lights up the little doorbell
1:34:27
light you know on the set or whatever it is. Um,  I often, as a matter of course, specify when I'm
1:34:36
putting together sound systems, specify interlink  equipment to attach to the lighting department,
1:34:41
even if the designer I'm working for hasn't  even said it once or the lighting designer hasn't talked about it either. It's just something  to be ready for. So, QLab is as good a show control
1:34:54
citizen as we can make it. We both send and  receive messages according to all those letters
1:35:04
and I'm going to go through them briefly um  so that we can understand how um the MIDI
1:35:15
messages are sent by a MIDI cue which is right  here using the old school five pin DIN port as an
1:35:23
icon. A MIDI cue has three tabs. Basics, which you  know about, triggers, which you're now expert in,
1:35:29
and the settings tab. And the first setting to  choose for a MIDI cue is a MIDI patch, which is
1:35:37
like any other uh just like an audio cue. A patch  is the way that a cue connects to a device. So,
1:35:45
I'm going to go into workspace settings to MIDI  and look at MIDI outputs because we have two MIDI
1:35:50
patches on this in this workspace. One is named  IA and that's connected to bus one or whatever a
1:35:58
disconnected MIDI device doesn't matter. The other  is named a MIDI device and it is connected to this
1:36:04
go box which can receive MIDI. And by virtue of  being able to receive MIDI, the go box tells the
1:36:11
Mac, here I am and I can receive MIDI. And the MAC  tells QLab, here's a list of all the MIDI receiving
1:36:18
devices attached. And so it appears on that list.  Those are all the settings for MIDI patches. But
1:36:27
because we um this list looks somewhat like  this list, it's worth pointing out a couple
1:36:33
of other things that patches can do. Notably,  um, all of the things I'm about to describe
1:36:40
work in MIDI patches, network patches, video  outputs, stages, um, we call them audio patches,
1:36:50
and that's it. You can hold down the option  key to drag and duplicate. You can reorder.
1:37:02
If you make a new workspace, you can open the workspace  settings for that workspace
1:37:11
and drag patches between to copy them.
1:37:18
You can also
1:37:24
select patches, one or all or several,  and drag them out of QLab into the finder.
1:37:31
and Cil will create a settings file with  the name of your workspace, MIDI outputs,
1:37:38
and three items saying, "Hey, you just put  three MIDI patches into the settings file."
1:37:44
That settings file can then be dragged into  a new blank workspace or any other existing
1:37:50
workspace. And those patches come with and  that works for MIDI patches, network patches,
1:37:58
audio patches, video patches. Yeah. But I  wanted to demonstrate them with MIDI because it's the the least settings available. So it's the  cleanest interface. So it's easiest to look at.
1:38:20
So we have a MIDI patch selected here and that's  the MIDI device that will receive the message
1:38:26
from the cue. Then we choose message type. MIDI  message MIDI cues can send one of three types of
1:38:32
messages. There's MIDI voice messages. There's  MIDI show control messages uh MSC and there's
1:38:40
MIDI system exclusive messages abbreviated to  CISX. We'll start with MIDI voice messages and
1:38:46
get through the others shortly. So don't worry. QLab  can send any of these types of messages: note on,
1:38:53
note off, program change, control change, key  pressure, which is also called after touch, channel pressure, and pitch bend change. And  again, that is a list drawn from the official
1:39:04
list of MIDI message types, which we thought were  the most common MIDI messages. I think one of
1:39:10
these got added after the initial invention  of the MIDI cue, maybe two tops. But again,
1:39:17
we await your instruction if there is a  MIDI message type. If you're like, "Man, I really need to use the breath control."  Great. Let us know. We'll put it in there.
1:39:26
It's not a big deal to add it, but we didn't  want this list to be long and unwieldy for no reason. Depending on what type of command you've  chosen, the uh attributes that are pertinent to
1:39:36
that command will appear below. So, here's a  note on message. It sends on MIDI channel one. We're sending note number one with a velocity  of zero. If I send uh a pitch bend, it needs a
1:39:50
channel and a value. And because pitch bend can  send um uh and because pitch bend is the kind of
1:40:00
message that might want to vary over time. Some  MIDI messages are fade-able. So you can check the
1:40:06
box and fade over duration from this value to  this value over this time using this curve.
1:40:18
the MIDI system exclusive message. Um, to explain  what that is, I need to just do a little history.
1:40:24
The folks in the 60s invented MIDI and they said,  "All right, we're going to have a set of messages that everyone understands. Note on, note off,  control change, program change, after touch, etc.
1:40:34
There were a bunch of them. There's more." But  then they thought, well, we don't know what the future will hold. So, we think that it would be  cool for every manufacturer of MIDI gear or MIDI
1:40:44
compliant gear to have a set of messages that is  exclusive just to them. We will call them system
1:40:52
exclusive messages. And anyone who joins the MIDI  consortium can apply for a MIDI system exclusive
1:40:59
code and then they get to have all the messages  that start with that code belong to them. It's
1:41:08
not very expensive to join the MIDI consortium.  It's some amount of money. And when you join the consortium, you can get a system exclusive  message. And for a little while, that seemed like
1:41:17
a very useful thing to do. So, for example, this  message is, as far as I can recall, this message
1:41:25
is the message that you send to a Yamaha DM1000  mixing console to bring the fader on input channel
1:41:32
4 to like 75% of fader travel. I think that's  what it is. 43 says the following is belongs to
1:41:43
Yamaha. 103E I think says this is a message meant  for the DM1000. 04 means input channel 4. 30 0C
1:42:00
means 75% of the fader travel. I can never  remember what the 09 means as much as I can
1:42:06
remember any of this stuff. And then all system  exclusive messages need to start with an F0 and
1:42:11
end with an F7. But QLab fills those in for you.  You may wonder why is it written in this arcane
1:42:19
way and that is because in their infinite wisdom  the MIDI people decided we will use hexadecimal
1:42:25
base to communicate MIDI messages. Hexadecimal is  base 16. So the valid digits in hexadecimal are 0 1
1:42:32
2 3 4 5 6 7 8 9 a b c d e f 10 is comes next right  in in base 10 we go 0 1 2 3 5 6 7 8 9 those are
1:42:44
all the single digit numbers and 10 is the first  two-digit number in hexadecimal it's zero through
1:42:51
f is all the one-digit numbers it's not super  important um but this is the way that you write it
1:42:59
Um, system exclusive is one of those things  that you do not need until you need and when you need often there's no other way. Um, before  OSC was invented, this was the way you controlled
1:43:10
complicated stuff via MIDI. Um, I mean after OSC  was invented, this is still the way you control
1:43:16
complicated stuff via MIDI, but reasonable  manufacturers have moved on to use something that's a little more human readable. Yeah, I  have a question from the chat. Oh, yes. Is what
1:43:26
would be uh what would be a possible preferably  simple solution to create a set of predefined MIDI
1:43:31
messages that can easily be recalled during the  show. For example, for sending fader control to a
1:43:37
mixer. Yeah, I mean the short my my short answer  is uh it would be better if you can use a mixer
1:43:44
that accepts OSC. Um but here's what I do. I have  a program that I'm a fan of called MIDI Monitor,
1:43:52
which might be on this Mac or might not. Is not.  Okay, no problem. I'm gonna install it real quick.
1:44:04
MIDI Monitor is a free piece of software.  Yes, allow, download, get the thing, do the thing is a free program which lets  you monitor incoming MIDI messages and
1:44:19
when MIDI monitor. Yes. I really sure  I want to open it. Yeah. Yeah. Yeah.
1:44:32
Sorry, fumbling my mouse.
1:44:42
Bye.
1:44:50
MIDI Monitor is a free piece of software  which lets you monitor incoming MIDI messages.
1:44:59
When you um open MIDI monitor, it will show you  all the MIDI sources that are available and one
1:45:06
of them hopefully is your mixer. With it open,  this this works with the DM100. And I know if
1:45:14
it works with every mixer, you want to configure  the mixer to both send and receive MIDI messages. When your faders move, grab the console, grab the  fader you want, and move it to the level that you
1:45:24
want. And you will see a stream of MIDI messages  come blasting in. The very last message is the
1:45:30
message you're interested in capturing. Because  the very last message is the message that says, "Get to this spot on the fader." Right? Because  that blast of messages that comes in as you move
1:45:40
the fader is, "Go to here. Now go to here. Now go  to here. And I go to here. And I go to here. That
1:45:45
last message, you can copy it and paste it into  a um and paste it into a MIDI 6x cue, being sure
1:45:58
to delete the leading F0 and the tailing F7  because QLB fills those in automatically for
1:46:03
you. If your mixer doesn't send MIDI system  exclusive messages when you move faders,
1:46:09
this is going to be a lot harder. But that is my  recommended method. My real recommended method
1:46:17
is to use a console that can communicate using  OSC or that um allows you to store a series of
1:46:23
presets on the console and just use simple MIDI  messages like a MIDI note or a program change message to recall the preset of your choice. Thank  you. And while I've interrupted you already, could
1:46:37
you double check that your screen capture outputs  are are running? We just were I don't know if we
1:46:42
we we lost the feed on the stream and I don't  know if it's on your end or on the other end, but I'll just since I've interrupted you already.  Is it resumed? Check. It might be on the other
1:46:53
end. So, thanks for thanks for checking.  Yeah, no problem. Great. We're back. Okay,
1:46:59
great. Uh I think what happened is that MIDI  Monitor I inadvertently asked Midi Monitor
1:47:04
to restart the computer and it quit Sienna  and that's what happened. But it's back now.
1:47:10
Um um yeah, so MIDI MIDI monitor is your friend.  There's also if you need a much more sophisticated
1:47:19
tool, it's a little heavier weight. Um Hexler  makes a program called Protokol. They spell it
1:47:25
with a K because it's cooler. Cool. Starting with  a K. Um Protocol is a fancy message receiving,
1:47:33
sending, examining tool. Highly recommended.  But MIDI monitor by Snoize is the standard
1:47:39
uh for me and has worked very well for me  for like 20 years. So I don't I don't argue.
1:47:49
Um okay, that's MIDI system exclusive. The next  type of MIDI message you can send is MIDI show
1:47:54
control message MSC. And what happened was um  Charlie Richmond of Richmond Sound Design who
1:48:02
does who did a lot of very creative um things with  MIDI in the 80s and 90s um and really impressive
1:48:11
audio playback tools uh as well. He was working on  things like roller coasters and and attractions in
1:48:20
theme parks and sending show control messages back  and forth between devices. And they were like,
1:48:25
"Okay, well, you're going to use MIDI because  it's robust and it's easy to understand and it's cheap to implement." So, okay, note one  will mean go and note two will mean stop. And
1:48:36
they had to come up with all these sort of like  in-house sort of temporary agreements about what
1:48:41
MIDI message meant what. And then he was like no  let's take the MIDI system exclusive system apply
1:48:49
for a system exclusive number and then create  a standard protocol for using system exclusive
1:48:56
messages as show control messages. So we will  create a go message and anyone that knows that
1:49:02
they're using MIDI system MIDI show control will  send the same message for go and receive the same message for go and everyone will know what go  means and that will allow folks like in the
1:49:13
distant future QLab to create a nice simple human  readable interface for MIDI show control messages
1:49:21
that will make it really easy to send things  like go and stop and whatever. So the way that
1:49:26
MIDI show control works is there is uh the first  thing you choose is a format for your message.
1:49:32
And a format is a pre-ordained list of types of  things that get messages like lighting general,
1:49:40
moving lights, color changers, strobes, lasers,  chasers, sound, general, music, CD players, EPROM
1:49:46
playback or EPROM playback, audio tape machines,  intercoms, amplifiers, audio effects devices,
1:49:52
equalizers, on and on to some of my favorites.  Machinery general, lifts, trusses, robots, barges,
1:50:02
process control general, hydraulic oil,  H2O, CO2, compressed air, natural gas,
1:50:11
pyrotechnics, fireworks, explosions, flame, smoke  pots. I especially like that category. I like that
1:50:19
there's explosions in this list. The reason I like  that is because it puts forth a kind of optimism
1:50:26
that I'm not really ready to embrace. That both  fireworks fl and flame will never be an explosion.
1:50:37
Not to mention the natural gas.
1:50:42
I'm here to tell you friends, we have no way to  be really completely sure that QLab is bug free.
1:50:52
Like actually no way. It's like can't be done  at this point. And the reason for that is not
1:50:59
only does QLab have QLab, which is under our  direct control, but QLab runs on the macOS,
1:51:07
which is decidedly outside of our direct control.  The macOS runs on Mac hardware and Mac hardware
1:51:15
is built to a standard of reliability that is  impressive but not absolute. We cannot 100%
1:51:24
guarantee that QLab will behave exactly a specific  way always and forever because we do not control
1:51:31
the entire apparatus that runs QLab. In theory,  we could write QLab in such a way that it only
1:51:38
uses software that we ourselves wrote. It was all  checked methodically and mathematically uh in a
1:51:43
way that could be guaranteed and it ran on custom  hardware that ran a custom OS just for us just
1:51:50
by us. This is how uh the space shuttle software  team was able to guarantee that there were never
1:51:57
going to be any software problems on the shuttle  and in fact there never were. Their process uh
1:52:05
was anytime any inconsistency or bug is found in  the space shuttle software, it is considered to
1:52:11
be a total system failure. Any bug of any kind was  regarded as in our simulation. The shuttle has now
1:52:18
exploded. And so there were never any showstoppers  in the software in the life of the shuttle program
1:52:25
because they were obsessive about it. They were  also working with an extremely constrained
1:52:30
set of parameters. The software that runs ran  on the shuttle is a game to this, right? It
1:52:41
ran on these incredibly esoteric processors that  were hardened against cosmic radiation. It used
1:52:50
handwoven memory uh conductive wire woven through  ferrite beads to produce uh a literal yarn of code.
1:53:02
Uh because that was impervious to cosmic radiation  changing a bit and therefore rewriting software on
1:53:10
the fly. Um we can't do that. We're not building  the whole widget. As a result, I want to tell you
1:53:19
that at no time do I feel really good about  anyone using QLab to drive fireworks. So, what
1:53:29
I do feel good about is if you've got a machine  that is hardened for safety, that is approved and
1:53:36
examined and engineered for life critical safety,  that is in charge of fireworks, that's great.
1:53:42
And if you want that machine to allow an incoming  message to tell it when to start the fireworks,
1:53:49
I also think that's okay as long as there is a  human person opening and closing that gate. Right?
1:53:56
So I have my fireworks machine here that's all  safe and impressive. I'm the fireworks operator. I
1:54:06
turn the key to say ready. I hold down the button  to say listen for a message. And then QLab says,
1:54:12
"Hey, fireworks go." That's okay with me because  then the person can let go that button, turn off
1:54:19
that key, and now if QLab wigs out because the Mac  was dropped off the desk or whatever, and it sends
1:54:27
another Fireworks Go message, the Fireworks  machine is no longer listening. Fine with me.
1:54:33
Not fine with me is QLab MIDI cable straight to  fireworks launcher. Don't like it and neither
1:54:41
should you. All and I mean all of the times that  something horrendous has happened with pyrotechnics
1:54:49
in a live event situation, it was something  that someone else could have done to prevent it. And not only could have prevented it, but any  reasonable person who was looking carefully could
1:54:59
have spotted the problem. Almost all the time  it's been obvious. Not all the time, but almost
1:55:04
all the time. And so here's I'm just giving you  one for free, right? Make sure that the thing
1:55:11
that actually does the fireworks is really made  for that. And then have it open a door to say,
1:55:16
I'll let you you tell me when to go. And then we  can have synchronize with the music where if the music is early or late, no one gets injured,  right? But if the fireworks are early or late,
1:55:26
perhaps someone does with me. Now I will describe  the rest of this. So once you've chosen the format
1:55:34
of the device that's listening, you have to  choose a command. What command are you going to send it? There is a fixed set of commands  in MIDI show control. Go, stop, resume, and
1:55:44
so forth. They're in all capitals, which is how  you know this is from the 80s because back then
1:55:50
lowercase letters cost extra. The message, the  command is chosen. Then the device ID is chosen.
1:55:58
Device ID is an address 0 through 127. And there's  some rules around this. Basically, every device
1:56:05
that wants to receive MIDI show control gets its  ID. Okay, I'm seven. And it gets its format. Okay,
1:56:11
I'm a barge and I'm seven. Whenever a MIDI show  control message comes in, it has its format,
1:56:17
barges, and it has its ID on the message, seven.  Oh, barges seven. That's me. I will listen to that
1:56:23
message. It's okay to have several barges all say  that they're seven. Then they'll all receive the
1:56:28
message. But if I'm over here and I'm barge number  eight, I see the message come in. That's not for me. I'm not moving. Or I'm over here and I'm like,  "Oh, I am my EEPROM playback because I'm one of the
1:56:40
four people who ever used one of those or whatever  it is." I'm I'm teasing. It's I take it back. Uh
1:56:46
I I'm some I'm a CD player and I see and I'm a CD  player number seven. And in comes the message. Oh,
1:56:51
but that's for barge number seven and I am  not a barge. So, nope, nothing happening here.
1:56:56
So you have to have both the format and the device  ID match. By convention, we also have all types
1:57:05
and we also have a rule where 127 is considered  the all call message. So if you send to format
1:57:11
all types and device ID 127, everybody responds  to that message. I'm a barge. I'm a CD player. I'm
1:57:18
fireworks. I go. I really I really love the  mental image of a CD player philosophically
1:57:25
asking itself whether it is a barge or not.  Am I a barge? No, I'm just a CD player. Yeah,
1:57:33
that's all I want to be. Short and stout. Here  is my whatever. Happy being a CD player. Frankly,
1:57:40
if I had to choose, I think I'd prefer to be  the CD player because I don't care for swimming.
1:57:47
Okay. But then you send a cue number and then a  cue list and a cue path. Cue number we've heard of.
1:57:54
Yeah. In MIDI show control, cue numbers must  be numbers. They can be decimal numbers but
1:58:00
they must be numbers. Cue list in QLab is  not a meaningful number. Uh because if
1:58:07
I have two lists in QLab, all the cues in those  two lists have to have unique numbers. Right?
1:58:14
So if I have a list called list one and a list  called list two, there's no such thing as Q1 in
1:58:20
list one and Q1 in list two because in QLab all cues  have unique numbers. But on an EOS as an example,
1:58:29
every cue list has its own set of numbers. So Q2  in list one is different from Q2 in list two on
1:58:39
EOS. Cue path is a parameter that I have never  seen implemented by anyone other than Charlie
1:58:47
Richmond. So, I'm not really sure what it is  and I know that you need it if you're working
1:58:52
with SoundMan Server or with the audio box.  Um, but I don't think you need it if you're
1:58:58
working with quite literally any other products.  But it's there because it's part of the spec.
1:59:09
So your format has to match. Your command has to  be a command the device can receive. Your device
1:59:14
ID has to match. Your cue number has to be a cue on  that device. And your cue list has to be either
1:59:21
um a list that's on that device or if you're  sending to QLab, it gets basically ignored.
1:59:27
And then when this message comes in, the device  does the command if all those things match. Yes,
1:59:33
the transmitting device doesn't need to have  any special setup. It just needs to have
1:59:39
um output to MIDI that is physically connected  to the receiving device. And that's MIDI show
1:59:46
control. I'm a big fan of MIDI show control. I  may not sound like it the way I talked about it,
1:59:51
but I actually am because I think it achieves  its goal, which is easier than system exclusive,
1:59:57
clearer than regular MIDI, all the advantages of  MIDI, which is that it's dead stupid simple to
2:00:03
build and physically maintain. It does have the  disadvantage of MIDI, which is that it's hard to get MIDI distributed around a venue. Electrically,  it's hard. Um, so I don't love it for that reason,
2:00:15
but if I've just got this thing plugged into that  thing, simple as can be. Really love it. Okay. And
2:00:22
that's all the things the MIDI cue can do. The MIDI  file cue is next. The MIDI file cue is here. It's got
2:00:30
the barred eighth notes. We know the basics tab.  We know the triggers tab. In the settings tab, we choose a MIDI patch and then the MIDI file cue  needs a target and that target is a MIDI file,
2:00:42
a MIDI file. I have chosen here a performance of  take the A train as recorded by Oscar Peterson
2:00:49
in June of 1991 sequenced and programmed  by Diane Luwendowski. Well done Diane.
2:00:59
These little dots are the visualization of the  data in the MIDI file. The MIDI file is a standard
2:01:05
format. It was described many years ago. It's a  standard file format for making MIDI messages.
2:01:11
This same file format will work on basically any  type of computer. And we only have one parameter
2:01:18
that you can adjust, which is the playback rate.  It needs a MIDI patch, which is a device that it
2:01:24
can go to. And that device needs to be plugged  into a device that can receive MIDI messages
2:01:30
out of a MIDI file. So it would make this thing  do something strange. But if I had a Clavinova,
2:01:38
which is a Yamaha piano that's got a MIDI me a  MIDI engine in it and has a little tiny motor
2:01:43
underneath every key on the piano. And I sent it  uh this message; it would play. You can take the
2:01:51
A train as though someone were sitting at the  piano playing. I've used MIDI files in exactly
2:01:58
one show in my life. We had a Clavinova on  stage. We had a person who was playing the
2:02:04
piano who was not much of a pianist. She  had to play a very difficult piece. And
2:02:10
um it's no knock against this individual. It's  a hard piece of music. And to find a great actor
2:02:16
who's just right for the part, who's in the right  town, will take that fee and is a killer pianist,
2:02:22
who can not only play this piece of music, but  can accurately play it as though she is exactly as out of practice as the character is. That's a  tall order. So, we just angled the piano so that
2:02:33
her fingers were not visible to the house. She  mimed playing it and we sent the MIDI file to
2:02:40
the Clavinova from the booth. And the Clavinova,  because it's not a synthesizer, it's a acoustic
2:02:45
piano with motors that drive the keys, played the  tune. Worked perfectly. 100% successful illusion.
2:02:56
Again, don't need it often, but when you need it, it's it's what you've got. If you are one of  those people who uses the MIDI file cue, tell
2:03:03
us about it. I'd love to know about it. I would  love to know more about those folks out there.
2:03:10
The next type of message that QLab can  send or receive is MIDI timecode. We've
2:03:16
talked about receiving timecode briefly, and  snarkily, but we also have a timecode cue, which can transmit timecode. The settings  tab of a timecode cue lets you tell the cue
2:03:27
to either transmit MIDI timecode or linear time  code. If you are in a situation in which someone
2:03:33
who is higher up the pay scale than you has  demanded that we're going to use MIDI timecode, you can sigh resignedly and know in your heart  that you are right and they are wrong and then
2:03:44
click over here to use MIDI timecode. Then you  can assign a MIDI patch which is the MIDI device
2:03:49
that will receive the timecode from QLab and send  it out to the world. And then you choose a frame rate. There are eight frame rates available and  then a start time and that is the first frame of
2:04:03
timecode that will get transmitted when you start  rolling the cue and then optionally an end time.
2:04:08
So this cue is starting at hour one minute zero  second one frame zero. If the end time is deleted
2:04:20
or uh it will show up exactly matching and that  means start and keep going till I'm I'm stopped.
2:04:27
But if you type in an end time that is different  than the start time, this MIDI timecode cue or this
2:04:36
timecode cue will start running by sending that  frame and keep sending a frame until it gets to
2:04:43
that time in which at which moment the timecode  cue will stop itself. So you can send an explicit
2:04:48
chunk of timecode from the cue. Frame rate in  case you are not familiar. Um these are film and
2:04:57
video times uh frame rates and that's because  timecode is originally a film and video topic.
2:05:02
Um it does not matter what frame rate you use. It  only matters that all the devices that are sending
2:05:08
and receiving timecode are using the same frame  rate. My frame rate policy when I'm working on
2:05:13
a show is I wait for someone else to say what  frame rate we're working at and then I agree.
2:05:24
You can also take the timecode cue and switch  to the vastly superior linear timecode,
2:05:30
at which point you must choose an audio device to  send timecode to. Hear my words. Time code does
2:05:38
not sound nice. Time code is made of square waves.  Square waves are the right waves to use if you
2:05:45
want to rip a speaker cone out of its surround  or permanently damage someone's hearing, or
2:05:51
absolutely melt headphones, right? No, Dave, that  would not sound cool. So before you run a time
2:06:00
code cue, think very very enthusiastically about  which cue output on which device you are sending
2:06:11
the timecode and really really ask yourself  whether or not that is where it belongs. Once you
2:06:18
have done that, you can choose a frame rate, start  time, and end time just like the other. Go away.
2:06:25
Go away. Go away. And you're off to the races.  Okay. Many people have asked over the years, how
2:06:34
do I get QLab to send timecode to itself? And the  most correct answer is, why would you want such a
2:06:42
thing? The answer to that is usually, "Oh, well,  I, you know, I want to have a bunch of cues that trigger along time and timecode." No. No. Do you  not remember the group cues? Do you not remember
2:06:52
the timeline group cue? The timeline group cue is your  friend. Make a timeline group cue, put your time
2:06:58
code cue in it, have that send timecode out to the  world, and then put your own cues in there and set
2:07:04
their pre-weights. And but for the most particular  scenarios, that is the superior approach. If you
2:07:13
are in one of those most particular scenarios,  we'll talk later, but in short, timecode going
2:07:21
out and coming back into QLab gives you nothing  that you can't already get inside QLab. Yeah.
2:07:31
Why? What doesn't go up to 60? So like I know 24 is the standard for film,  but is there a reason why like you wouldn't
2:07:40
do 60? So Oh boy, here we go. So video speed  and film speed are things. Yeah. And 60 frames
2:07:55
a second is sometimes 59.97 frames per second.  um timecode started in cinema and these are the
2:08:07
um film and video speeds that are common. That is  the best answer I can give you right now. To the
2:08:15
best of my understanding, I don't know of anyone  who's I've never seen a a context in which time
2:08:21
code was being run at 60 frames or 59.97 frames  per second. I'm not saying it's not possible,
2:08:26
but I've never seen it. So, I don't know enough  about it to give you a more thorough answer than that. Um, I also don't like if I'm completely  honest with myself and with you all don't deeply
2:08:40
understand the difference between drop frame and  non-drop frame. I like I vaguely understand it, but like why? Like I don't really understand why.  Whereas like 24 frames per second is the standard
2:08:53
for film because that is the basically minimum  frame rate that looks good. And so that's the
2:08:59
way to maximize financially how much movie you can  shoot on a specific amount of film. 25 frames per
2:09:06
second exists because electricity in Europe runs  at 50 Hz. Honestly, 30 frames per second exists
2:09:16
because electricity in North America runs at  60 Hz. And then all these ones with decimals
2:09:21
have to do with how irritating it is to get film  and video to agree with each other. But that kind
2:09:27
of is the limit of my knowledge and sort of on  purpose because if I knew more I'd be asked to
2:09:33
do more with timecode and I don't want to be. Our  our colleague Siobhan is is deeply an expert about
2:09:41
timecode and we have in the past occasionally uh  when we've met up as a company we've done a game
2:09:48
where Siobhan tells us the history of timecode  and every time an unfortunate technical decision
2:09:53
was made everyone takes a drink and it's a long  night let me tell you it is a deep and
2:10:02
just really head-scratching history of how timecode  got to be the way it is. But it is pervasive.
2:10:11
It's used everywhere and you want to know only  just the right amount to be able to use it when you need it and try to avoid it otherwise. Yeah,  that is also how I feel. Okay. And now good stuff.
2:10:29
OSC, which is to me the um the show control  language of choice. OSC was invented by some
2:10:41
lunatics at UC Berkeley a while back. Um I  say lunatics very lovingly. Many beautiful, wild,
2:10:49
unbelievable things have come from UC Berkeley  over the years. Among them, my brother who went
2:10:55
to UC Berkeley for journalism school. The  CNMAT, the Center for New Music and Technology,
2:11:06
I can't remember how what it stands for.  They they're the the the new music folks at Berkeley invented OSC because they were sick  of doing nonsense with MIDI that was above its
2:11:16
pay grade. So they thought wouldn't it be cool if  we could invent a language for show control where
2:11:22
instead of a fixed set of commands go stop reset  and note on note off program change we could say
2:11:30
the protocol is every device every controllable  object has its own library of commands and if
2:11:37
you want to control that object you send it one  of the commands in its library and it knows what to do with it and they created a format of message  that is human readable form looks like this. It's
2:11:50
divided with slashes like a URL is. And um this  message slash q/99/ pre-weight with a big W then
2:12:00
a space and then 4.2. This is an OSC message  out of QLab's dictionary. That part is called
2:12:09
the address of the message. That part is called  the argument of the message. The rule
2:12:17
in OSC is there are some messages that are only  addresses. Those may not contain spaces. There
2:12:25
are some messages that are addresses plus one or  more arguments. In QLab, we separate the address
2:12:32
from the argument with a space and we separate  arguments from each other with space. But this
2:12:37
is the human readable form of a message that  computers send to each other. The actual message
2:12:43
is not plain text, it's encoded. So the space is  just a human decision about how to display the
2:12:50
difference between the address and the parameter.  You could have a different interface. You could say the address goes in this box and then we'll  have some number of boxes below and those will be
2:13:00
the parameters. Other com uh other software uses  a comma to separate the address and the arguments.
2:13:08
There's no better or worse. I mean reasonable  people may differ but the point is this is not the actual message. This is the human readable  form of the message. Just like note on is not the
2:13:19
actual MIDI message, right? It is some series of  binary numbers. Does that make sense? Okay. Great.
2:13:29
One thing that is true uh as we pass  through though is it will matter in
2:13:34
subtle ways like the space will start to  matter. If you want to send a message with an argument and the argument contains  a space, how can you make it clear that
2:13:44
that space is part of the argument rather  than a separation for a new argument? So, we'll show you in a bit. This message tells  QLab to set Q9's pre-weight to 4.2 seconds.
2:13:58
If we look over in QLab, we've got a network cue,  which is how you send OSC messages in QLab. And
2:14:05
this network cue has a um in its settings tab a text  field to type in an OSC message. The settings let
2:14:14
you choose a patch and there are many on this  computer. Lets you choose whether the message
2:14:20
fades or not. We'll get to this in a minute. And  its duration. A message that is not set to fade
2:14:26
doesn't need a duration. When you run this cue,  it will send this message once instantaneously.
2:14:32
If I give it a duration, it will resend  this message at this frequency for for
2:14:40
that duration. So, it's not really that clear  why you would want to send set your pre-we to
2:14:48
4.2 30 times a second for 6 seconds, but  it could be done. We'll talk more about
2:14:53
duration and time in in in a minute. When  you send this message to a copy of QLab,
2:15:02
if there is a cue that is cue number 99 in that  copy of QLab, its pre-weight will be set to
2:15:07
4.2 seconds. And indeed, I have configured  this patch to send OSC messages into QLab
2:15:15
itself. And when I run it, you'll see that  Q99's pre-weight, bam, is now set to 4.2.
2:15:25
That's nice. On the one hand, you can just reach  over and type in 4.2, but on the other hand,
2:15:32
you have to be at the computer to do that. Maybe  I would like someone over here on a DiGiCo console
2:15:43
mixing a show watching an actor walk upstage and  wanting to delay a message for a cue based on
2:15:53
the distance upstage of the actor. Send an  OSC message from the console and say, "Hey,
2:15:58
console, tell me the actor's position, send  that as pre-wait time to QLab. Some kind of
2:16:05
nonsense like that. Or maybe I have um Alec,  what's it called? The tracker that you like.
2:16:16
You put a thing on and you put cameras up and uh  Zack Track. Zack Track. Thank you. Maybe a Zack
2:16:22
Track system can be configured to send Q99/pre  and then fill in a value based on the location
2:16:28
of the tag. Black Track's heard of I've heard  of also, but Zack Track is what I was thinking
2:16:34
of and not thinking of the name. Yeah. Yeah.  Yeah. Yeah. I just said just like Yeah. Um
2:16:45
so that is the basics of sending an OSC message.  There are out there many good citizens of the
2:16:52
OSC world which are not sound. And so in a sense  the S in OSC which stands for open sound control
2:16:58
is a bit of a misnomer. Um, sound is where it  came from and we get not that much glory among
2:17:04
our lighting and video brethren. So, we feel like  we're going to claim this one and OSC is sound and
2:17:13
sound meaning sound. Uh, not just sound. Um, ETC  lighting consoles have a phenomenal OSC library.
2:17:23
Um, uh, d&b. Behringer. I have nothing nice to  say about Behringer except their embracing of OSC,
2:17:31
which is pretty impressive. Um, Yamaha these days  has really gotten on board with OSC. Meer Sound
2:17:39
is very on board with OSC. There's a lot of groovy  stuff out there that can be controlled by OSC and
2:17:44
can control using OSC. And because of that, QLab  can sort of sit in the middle of a show control
2:17:53
context and tell different devices to to do what  they're doing um based on information from other
2:18:00
devices and it becomes really interesting what  can be achieved now because there are so many
Network patches and network device descriptions
2:18:06
devices out there that can speak OSC and because  the the paradigm of OSC is each device has its
2:18:13
own library of commands, it gets tiring to  write out all these messages if you're doing a
2:18:18
lot of it. If I'm sitting in a theater and  I'm sending messages from QLab, A to itself,
2:18:24
B to a DS100, C to a Meyer Galileo, D to an EOS  console, E to a, I don't know, some other thing,
2:18:32
a Pixera server. I've got to have like all these  manuals open, flipping through trying to find the
2:18:37
right message to send to each device. So we have  something called network device descriptions in QLab 5
2:18:49
You can create an a network cue patch which is  attached to a device description and instead of
2:18:58
presenting you with one big text box to write  in an OSC message, it will present you with a series of hierarchically organized controls that  let you navigate your way to a specific message.
2:19:09
because QLab contains the library of messages for  the devices. I'm going to show you how to do that.
2:19:16
We're going to go to workspace settings, network,  and for a moment, just don't get overwhelmed
2:19:23
with all the stuff you're looking at on your  screen and zero in with me on just this row.
2:19:32
The name for the patch, QLab parenthesis OSC. It's  just a name. It's a human readable name like every other patch. The type is OSC message. Network  cues in QLab can send whichever type of message
2:19:47
their patch dictates. You can send an OSC message.  You can send plain text using UDP. You can send
2:19:55
hexadecimal codes using UDP or you can send a  message that is defined by the network device
2:20:04
description that the patch is using. So this  message QLab template uses the QLab 5 library.
2:20:17
This message uses the ETC EOS family library. I'm  sorry, this patch. Does that make sense? So when
2:20:27
I create a cue and I send it to ETC Nomad network  cue patch ETC Nomad, where are you? Oh, yeah. There
2:20:39
I get a list of OSC messages that EOS knows what  to do with. I want to send a channel message. Do I
2:20:49
want to specify the user? Yes, I want to say user  2 is sending or user two is sending this message.
2:20:55
And I'm going to choose uh I want to set a  channel at level. I want to set channel 89 to 45.
2:21:06
And then down here in the bottom, QLab shows  you the actual OSC message that's getting built. /eos/user/2/chan/89 and then one argument  45. When I send this message to an EOS console,
2:21:21
if that console is set to allow messages to allow  control from user 2 and that console is set to
2:21:27
allow incoming OSC messages and that channel  that that console has a channel 89 in its patch,
2:21:36
then sending this message will bring that  channel 89 to 45%. Which is great, right?
2:21:46
Because then you could have a QLab computer that's  like your space maintenance for a rehearsal hall,
2:21:54
your space maintenance tool. The computer  could be sitting there running. You've got an EOS rack mounted thing and channel 89  could be the work lights in that room. So
2:22:06
the crew can come in and run the cue on  QLab that's just like work lights up please without having to go and do slightly more  complicated interaction with the EOS rack.
2:22:18
And this whole hierarchy means you don't  have to remember this syntax for EOS,
2:22:24
which is hard to remember. I mean, it's not that  hard, but it's hard to remember, especially when you start to think about all the huge piles of  messages that each device can use. If I'm remote
2:22:34
controlling a DS100 and I'm going to end scene  positioning or function group spread factor like
2:22:43
okay /dbaudio/1/functiongroup/spreadfactor/4  space 1.19 like you're going to remember all
2:22:50
of these. No thank you. Spend your time designing  your show. Let the robot do the robot stuff.
2:23:01
We have in QLab 5.5 organized our network  devices by category. So under audio,
2:23:14
we can control all of these devices. Under  automation, we can control these devices. Hey,
2:23:20
Zac Track, there it was. Under communications,  we can control these devices. Under lighting,
2:23:26
these devices. And under video, these devices.  you'll see that um uh oh I just learned that atemOSC
2:23:35
has reached end of life and has been  replaced by a different product. So we have to change that. Um if you're listening to this  and you have a device that you want controlled
2:23:49
by OSC and QLab and you think it should be  among this this list, let us know about it.
2:23:54
All we need is a comprehensive manual describing  what OSC messages your device can receive and that
2:24:02
it is in some way readable and then we will make  it. Um, notably um there are a few out here that
2:24:10
I want to sort of call out uh well because  they're my favorite to call out. I will call out Behringer. It's a bad citizen of the world  for many many reasons. But one of the reasons
2:24:19
they're a bad citizen of the world is that there  is no published spec for the X32 OSC library. The
2:24:26
authoritative document that shows the list of OSC  commands for the Behringer X32 was created by some
2:24:33
guy who hooked up his Behringer to Wireshark and  just sniffed all the messages coming out of it. I
2:24:41
think that's reprehensible. If you're going to put  something in the world and you're going to bother
2:24:46
to write a manual for it in the first place, go  all the way and have the manual actually describe what the thing does. What? Yeah. Really, really  frustrating. So, it took us a while to get the X32
2:25:01
in here because it took me a while to read through  that document that that guy wrote. Uh, likewise in
2:25:06
lighting, this is a sort of different story. The  Grand MA3, which is not a simple piece of hardware
2:25:11
at all. The Grand MA3 uh their OSC library is  so flexible um that like you can basically sit
2:25:22
at the Grand MA3 and tell it here's how I want  you to listen to OSC. So there there is actually
2:25:28
a fairly small library of fixed commands and a  fairly large library of it could be anything.
2:25:34
So it took us until it took us a while until a  Grand M3 expert communicated with us about the
2:25:40
set of commands that are fixed and the set that  aren't flexible. So it it's a little bit difficult
2:25:45
to decode some of these. Um and all of that stems  from a good thing which is that OSC messages are
2:25:52
flexible. Okay, while we're here I want to talk  about some other things in the patch that are a
2:26:00
little headbendy but worth knowing. To begin with,  patches can send uh to begin with patches can send
2:26:08
uh messages either using UDP or TCP. UDP which  stands for universal datagram protocol and
2:26:16
TCP which stands for transmission control protocol  are two very low level, very "don't need to worry
2:26:23
about it almost all of the time" components of  computer networking. And the short of it is
2:26:31
some messages need to be one kind, some messages  need to be the other kind, and some messages can be either kind. Um, and until you really need  to know more, it's just going to be cluttering
2:26:43
your mind. So on a small network, not connected  to the internet, if your device can use either,
2:26:52
you can use either. The more complicated your  network, the more important it is to use TCP,
2:26:58
which has better traffic cop facilities. UDP is  a little more fast and loose. That's as far as
2:27:05
I'm going to go on that right now. We can talk  more if you like. The next uh menu, interface,
2:27:11
allows you to select one of the spec one of  the specific network interfaces that your Mac
2:27:16
has as the interface that these messages will  go along. Or you can leave it as automatic.
2:27:24
If you're connecting your MAC to multiple  networks and those multiple networks all
2:27:30
use the same IP address scheme,  which is 1 192.168.5 something,
2:27:37
if if I'm on two networks that are both 192.168.5  dot something, then it's possible that QLab will choose
2:27:44
the wrong network to send my message over. So  that's when I would choose an interface here.
2:27:51
Nearly all of the time that I leave this  on automatic, it works perfectly. Almost every time. Only when I have set up a bizarre  network situation, have I needed to choose the
2:28:01
interface. Next, you choose the destination,  which is the IP address of the device that
2:28:07
is receiving the messages. If IP address is  not something that you feel comfortable with,
2:28:18
I encourage you to go to the doc to tutorials
2:28:23
to basic networking. I wrote this article  after getting frustrated with explaining
2:28:30
IP addresses at the right level of  detail for stage hands and designers.
2:28:36
This is written out to explain basically all the  things you need to know for IP addresses to use
2:28:41
them effectively in the theater and a minimum of  stuff you don't need to know about IP addresses to
2:28:48
use them effectively in the theater. In short, IP  addresses are four numbers separated with periods
2:28:57
until we go to IPv6, which is coming real soon  now and has been for a decade. A decade longer.
2:29:05
two. Yeah. 20 years. Yeah. Uh, incredible.  But for it's a number dot another number
2:29:12
dot another number dot another number. And  those numbers are all between 0 and 255. Um,
2:29:18
but they're usually neither zero nor 255. But  sometimes they are, but sometimes they're not.
2:29:26
Then there's port number. So in theory, the IP  address described is the address of a computer.
2:29:33
Just like 10 Liberty Street is the address of my  house, right? In theory, this computer's address
2:29:42
while it's connected to this Wi-Fi network is  a specific number that's only for this. So if I know the number, your 1.2.3.4, then I know that  messages that sent to 1.2.3.4 end up here. Port
2:29:54
number is like apartments in the building. So, I  send a message to, you know, 123 Anywhere Street.
2:30:03
Okay, great. I'm at the building. Um, there's  100 apartments here. Which apartment gets it? That's the port number. So, port 53,000 is QLab's  apartment. You can change the port. We'll talk
2:30:16
about that some other time. But in short, you need  to know both the address of the receiving device
2:30:21
and the port number of the software or program or  subsystem or whatever that is listening for OSC
2:30:30
messages. If you use a network device description,  QAD can will fill in the port number for you to
2:30:36
the default that the manufacturer of that device  specifies. But you always might have it customized
2:30:42
and you need to know, hey lighting folks, are  you using port 8000 like usual or are you using a different port on this particular show and they  will tell you or they will often say, I don't know
2:30:52
what you're talking about. Please leave me alone.  I'm busy doing lighting. In which case the answer is they're using port 8000. Passcode is a QLab  specific additional security measure
2:31:07
in which messages are checked against  the passcode and only allowed in if they have a
2:31:15
matching passcode. You can set your workspace  to also allow messages with no passcode. But by
2:31:23
default in the OSC access tab, which we will talk  about in greater detail in just a bit, you have
2:31:29
to have a passcode that allows messages coming  in. And then incoming messages have to have that
2:31:35
passcode in order to get in and do stuff to your  Mac. Fear not, we will return. But we're already
2:31:42
we've already said too many numbers in a row. So,  it's I need to break it up, intersperse it with
2:31:48
something a little more action-y before we're all  ready for more numbers. These are network patches.
2:31:59
Here's another network cue that's sending uh  an OSC message to a Meer Galaxy. Just showing
2:32:07
you how another way that it might look when  you're using a network device description.
2:32:12
Here we're controlling the device output  4 and setting its voltage range to
2:32:17
+16 dBu which is the kind of granular  control that we all expect from Meyer.
2:32:26
Now when you give a network cue a duration last week  spending time with my little nephew and he likes
Network cues with duration - resend, 1D fade, 2D fade
2:32:36
if you give a mouse a cookie and I realized if  you give a network cue a duration it will probably ask you for a glass of milk. When you give a  network cue a duration, we saw earlier that you
2:32:47
could resend the message over the course of that  duration. One of the reasons you might want to do that is if you have a congested network and  you want to make sure the message gets through,
2:32:56
even if there's uh extra traffic on the network,  right? Set the cue light to red, please set it red.
2:33:04
Set it red. Set it red. I'm going to send this  message a bunch of times over five seconds.
2:33:09
But another reason you might want to have a  duration for a network cue is to send a range of
2:33:15
values to like drive a fader or move an object.  So I am sending this message with a duration of
2:33:25
10 seconds and it's going to send what's called  a 1D fade, a single access fade. One parameter
2:33:32
is going to change value over the course of these  10 seconds. We're going to send messages every 20
2:33:38
20 times a second, 20 frames per second. And  we're going to send floating point numbers,
2:33:44
which means the range for this message is  going to start at one and go to zero. And
2:33:50
it's going to send every decimal number it can  in between one and zero. So one, .9999, .9998, .9997,
2:34:01
20 times a second for 10 seconds.  When I send this message,
2:34:08
which sends opacity messages to those cues,  it drops their opacity down over 10 seconds,
2:34:17
lifts their opacity back up using this  message, which fades from zero to one
2:34:27
and stops them. But now that was one message  controlling several cues. How did I do that?
2:34:33
The answer is the next superpower of OSC is  that it supports wild cards. A wild card is
2:34:42
a special symbol which means more than one  thing. So you remember that this cue was Q98.
2:34:54
That 99 gets matched over  here by this cue number 99.
2:35:02
But this message is /cue/osc*. And here I  have three cues numbered osc1, osc, and osc3. The
2:35:12
star says anything will do here. So when I  send a message to /cue/osc*, what I'm saying
2:35:22
is send this message to any cue whose cue number  starts with OSC and then after OSC has any text.
2:35:32
So I can send one OSC message and  those three cues will all receive
2:35:38
it because their names match the pattern  defined by this asterisk. Are you with me?
2:35:50
2D OSC fading is also possible. So if  I set the fade menu to 2D fade. Oh,
2:35:57
I'm sorry. I'm going back. I skipped something.  The fade is facilitated also by this little
2:36:05
uh construction, hash V hash. In  a 1D fade, the V surrounded by
2:36:14
hash marks is a code saying fill in  the fading value here. V for value.
2:36:22
this hash sign, or if you're my age, pound sign,  or, if you're 50 years older than me, octothorp,
2:36:31
which is the typographical name for that symbol,  is used like quotation marks to surround what we
2:36:38
call here a token. A token is something that  gets filled in with something else later. So
2:36:45
we have one token in a 1D fade that is V for  value. And the value that gets faded along
2:36:52
this curve here gets filled in in place  of that V every time the message resends.
2:37:02
When we set this fade to 2D fade, we get  a what should now be familiar to you,
2:37:07
canvas view with the same tools that we use to  draw paths for object audio. We can make it this
2:37:19
canvas any width or height we like. We're not this  is not a map. We're not going and assigning a map. It's just for this cue space. And here I'm  sending /cue/soup/translation. And then
2:37:33
I have two arguments both of which are tokens  hash x and hash y. X means the X-axis position of
2:37:41
the pip that's going to fade around this space and  y means the Y-axis position. Cue soup is up in here.
2:37:51
Hello soup. So, when I run this cue, nope, had  the wrong cue standing by. When I run this cue,
2:38:06
oh, it had a pre-wait, the X and Y position of that cue on  this stage gets modified by this path.
2:38:22
For a while, this was the only way to do  something like this in QLab before we added
2:38:27
2D fades to video, which we haven't talked  about yet because it's not after lunch yet.
2:38:33
But this is a 2D fade of an OSC message.  Now, we say 2D and you think of like this,
2:38:41
right? But it's really just any two parameters.  So the 2D fade, if I sent it to an input channel
2:38:49
message on a console that was appropriately  configured, could be level and pan or could
2:38:54
be any two values that are two arguments in an  OSC message. It could be hue and saturation.
2:39:04
You have to have an OSC message that has  two arguments like this. If there's an OSC
2:39:10
message you know of that's like /my/groovy/message  and then argument argument argument
2:39:16
it's three arguments you could say well  argument one will be x argument two will
2:39:22
be just the number seven and argument three  will be y maybe that's red green blue we're
2:39:27
going to change the red and change the blue but  leave green alone. So, as long as there's two
2:39:33
arguments available to to replace with hashes,  you can use that message in a 2D fade. You with
2:39:42
me? A little. It's hard because it's it's  hard to pin down when there's no specific
2:39:47
example and it's hard to come up with specific  examples that aren't excruciatingly specific.
2:39:56
Are there any questions here?
2:40:03
Okay, time to sit down. Now, if you recall yesterday,  I discussed um the frustration that can exist
2:40:17
when show control messages are sent from  one department to another during a break or during a hold when folks are expected  to be doing independent parallel play.
Override Controls
2:40:29
One of the tools that we have in QLab which  helps you manage this is the overrides window
2:40:35
which I want to discuss now because it's  most relevant to everything we just did even though it's a slight change of topic  but it's a good size topic for between now
2:40:42
and lunch. I'm going to go to the windows man  the window menu and choose override controls
2:40:51
and bring this panel up here. The override  controls window lets you temporarily enable
2:40:59
or disable different kinds of messages that  can come and go from QLab. To emphasize,
2:41:06
the overrides control window is absolutely in  charge. When I turn musical MIDI output off,
2:41:15
no MIDI voice messages get out of QLab. Period.  when I turn it back on, maybe some other reason
2:41:25
could stop them. But when it's off here, it is  definitely off. So if I'm sending OSC messages
2:41:33
to all kinds of devices, I can send external  out I can set external output off. And now
2:41:42
all OSC messages that leave the computer and go  somewhere else are disabled. So, I can turn all
2:41:49
of this off while I'm on hold and not bother the  lighting people, not bother the other devices,
2:41:57
not do anything over over there. But local output  is on. That means that OSC messages which come out
2:42:05
of QLab and come back to me here in QLab are still  permitted. I went past this a little too quickly.
2:42:17
When we talk about IP address, there's one special  IP address, localhost, which means me. So when you
2:42:25
set an uh a QLab network patch to localhost, that  message never leaves QLab. Now folks with some
2:42:34
programming experience are probably expecting  localhost to be the same as that. But in QLab,
2:42:43
it is not the same. 127.0 0.0.1 means the same  computer. Local host means stay inside QLab.
2:42:59
So, oops, did not mean to do that. So,
2:43:04
local output is separated from  external output for network messages.
2:43:12
We also have the ability to turn timecode input  and output off and to turn DMX output off. It used
2:43:19
to be true that this only disabled ArtNet lighting  output and not Well, I've disabled my out lighting
2:43:25
output. And there's a two-c delay in the firmware  of the lighting controller. When I reenable it, it
2:43:33
wakes right back up because it starts hearing from  QLab again. Um, we'll talk about lighting tomorrow.
2:43:42
Input works the same way. And I want  to call your attention to the footer of the workspace. When different inputs  are disabled, QLab tells you about it
2:43:57
and the message gets long and longer the more  things are disabled. When outputs are switched on,
Workspace Settings - OSC Access, passcodes, ports
2:44:07
you will start to see zero with a slash in the  uh status column. That icon means overridden.
2:44:17
The mnemonic here is the O makes you think  of override, I hope. And the slash means no,
2:44:24
not this. So that means that the cue, there's  nothing wrong with the cue, but its output is
2:44:30
being suppressed because there's an override  that's preventing it from outputting. Yeah.
2:44:49
Yeah. Yeah. Um you can set um you can use Apple  script uh and OSC to control these buttons.
2:45:02
So, when I'm doing a show with a lot of time  code or I'm sorry, with a lot of show control,
2:45:08
I will make a um cue in QLab that uses  scripting to toggle the buttons I want
2:45:16
toggled off and then another script that  toggles them on. And I will set a button
2:45:21
on my MIDI controller. Just when I hit  that button, that that toggle is flipped.
2:45:31
Do you need it? Uh, you need you need  either Apple script or OSC. Yeah. And
2:45:43
if you're ever going to disable OSC output,  then you can't use OSC to turn it back on.
2:45:52
Um, but since scripting cannot be  disabled by the override control panel, I use scripting just to make completely  sure. Okay, any other questions here?
2:46:07
Override controls. It's a  window to make friends with, right? I know plenty of lighting folks who  just whenever the stage manager calls hold,
2:46:16
they reach around behind the lighting console  and unplug the network cable that plugs the computer into the show control network.  And I'm like, I got a button that's nice.
2:46:27
do you want to trust me? And they're like,  "No, no, I don't." Um, but it's fine.
2:46:43
Network cues themselves. I always do this  in this class. I always forget that I have a
2:46:48
whole little separate shorter list of things to  talk about network cues with. All right. Well,
2:46:53
that's how that goes. Um, so instead I will just  um move on to the bottom portion of this list. So
2:47:04
OSC access I started talking about this but now  it's time. I said too many numbers. We got to go do something exciting. We'll come back and do  more numbers. It's time more numbers. In workspace
2:47:14
settings network OC access there is a checkbox  to allow or not OSC to come into this workspace.
2:47:22
If I turn that checkbox off, no OSC messages  make it into the workspace. OSC messages still
2:47:28
make it to QLab. You can send some messages  to QLab itself. Messages like, "Hey, QLab,
2:47:35
tell me a list of all the open workspaces. Um, but  the workspace itself is prevented from receiving
2:47:42
OSC if that box is unchecked. Over here the  IP address or addresses that the computer is
2:47:50
currently holding are listed so that you can  see what address should I be sending messages
2:47:55
to in order to get OSC into this QLab uh into  this copy of QLab. Now you have to figure out
2:48:03
on your own if there's multiple IP addresses  whether one of them or the other is on the correct physical network to send OSC from another  device but at least gives you a starting point.
2:48:16
Passcodes as I said before are a security  mechanism which um prevent unauthorized OSC
2:48:24
messages. I have here a little table of passcodes  and you can add as many passcodes as you like.
2:48:33
Each passcode in and no passcode can each be  assigned to three layers of permission. View,
2:48:40
edit, and control. If view is unchecked,  then no message that has the corresponding
2:48:48
passcode will will successfully arrive  in your workspace. With view checked,
2:48:56
messages which only ask questions but don't change  anything will be permitted. With edit checked,
2:49:05
messages can edit parameters in QLab but  can't start, stop, start cues, stop cues,
2:49:13
or move the playhead. With control checked, OSC  messages can start cues, stop cues, and move the
2:49:21
playhead. But with edit unchecked, they won't be  able to edit anything. And with all three checked,
2:49:27
you have full access. So I could create a  set of passcodes where my operator can send
2:49:37
OSC messages that do control messages, but not  edit messages. My associate designer can send
2:49:43
edits but not control because I don't want the  associate designer to accidentally run a cue.
2:49:49
And then um uh full access is possible with this  third passcode for rehearsal and programming time.
2:50:00
By default, QLab listens on port 53000, but  you can customize that port on a workspace by
2:50:08
workspace basis. QLab also listens for plain text  over UDP. And if you type out the human readable
2:50:17
form of an OSC message and send it to QLab, QLab will  try to interpret it as an OSC message and execute
2:50:22
it, you can send that to port 53535 or to a custom  port of your choosing set here. Make sense? Okay.
2:50:34
I find this passcode stuff really useful some of  the time and it gets in my way some of the time if
2:50:41
I'm on a network that is physically controlled.  Well, then I don't have to worry about passcode
2:50:47
access because no one's getting on the network  without coming to me. So, I am pretty liberal
2:50:54
with my checking of these boxes for no passcode.  A lot of software doesn't know how to send a
2:51:00
passcode to QLab because it's a QLab specific thing.  Some software can't really be well configured to
2:51:06
send passcodes. So, if you're using that stuff,  maintain physical control of your network. Enable
2:51:12
access by no passcode and you'll be fine. Yeah.  And when I say physical control, I mean I have no
2:51:19
Wi-Fi network. I have a network switch that's in  a place where no one can just reach in and plug
2:51:25
in. Then how could someone get on the network?  They can't. Or if the network switch is by the
2:51:31
knees of my operator standing at the mix position  and some hoodlum comes in with a laptop and an
2:51:40
Ethernet cable ready to just change the color  of all my cues or pre-weight times be damned,
2:51:46
right? They're going to the operator's going  to notice. They're going to be like, "Hey kid, what are you doing there trying to plug into my  network switch? Get away." And so forth. Questions
2:52:00
questions? like why did you use the word  hoodlum yeah we might be getting this later
2:52:05
but what's the difference between connecting to  a workspace via OC from another key lab versus
2:52:11
the connect workspace yeah so we will talk about  collaboration tomorrow but in short collaboration
2:52:19
uses its own communication protocol and not OSC  and collaboration only works with another copy
2:52:26
of QLab OSC can come in from anything. So if you  have an EOS lighting console over there and a DiGiCo
2:52:38
sound console over there and a D3 server over  there, those devices can all send OSC messages
2:52:44
to QLab. None of them can use QLab collaboration  because QLab collaboration is a QLab only feature.
2:52:52
So if I want messages coming  in from those devices, I must allow OSC connections. If I want  collaboration from another copy of QLab,
2:53:01
I must go to collaboration and allow  collaboration connections. But being able to turn those on and off separately has value.  Likewise, I'm sorry, remote uses OS for now.
2:53:22
Likewise, in that context where I have an EOS, a  DiGiCo, and a D3 server, it might be convenient
2:53:29
to have three passcodes, one for each of them if  their software can send a passcode. And then I can
2:53:36
individually disable or enable those passcodes to  say like right now I'm not taking any calls from
2:53:41
the DiGiCo and just disable the DiGiCo's passcode, but  I'll still get messages from the EOS and from D3.
2:53:51
I'm not sure that that's useful, but it could be.  Yeah. All right. Because video is a big topic,
2:54:01
I first of all don't want to start it until after  we've all eaten so that the blood sugar is up, so
2:54:08
that the attention is up. Second of all, I don't  want to interrupt it. So, because we are we have
2:54:14
an asymmetrical amount of day. Yesterday we had a  longer morning and a shorter afternoon. I'm going
2:54:20
to propose to you that because we've come to a  good breaking point in the um order of operations.
2:54:27
We could break for lunch very shortly and then  return and spend the rest of the day on video.
2:54:33
Does that feel reasonable? Is anyone just itching  for more of the topics that we've been doing so
2:54:39
far today? Feeling underserved in this area? You  are. Can you describe the nature of your interest?
2:54:53
Okay, great. That's great. Um, I think then we'll  go like another 10 minutes or so because there's a
2:55:04
little bit more networking to talk about. We'll  spend like 10 more minutes on networking or so.
2:55:09
Then we'll go to lunch. We'll come back and do  video. And if there's still more to go beyond
2:55:15
those 10 minutes, don't be shy. That will be part  of our tomorrow plan. Does that sound good? Okay,
2:55:21
great. There's a few other tricks QLab  does with networking that I want to
2:55:27
um point out. The first one I want to talk about  is OSC queries. This is something unique to QLab.
OSC Queries
2:55:36
This is not OSC in general. I want to call  your attention to uh the cues here T1 and T2.
2:55:48
These cues send messages to QT2 setting its  color name. So this sets T2 to red. This
2:55:59
sets T2 to no color. This message is a little  differently structured. QT2 color name which is
2:56:11
the address that we've been using for these  last few messages. But then the argument is
2:56:17
another address surrounded by hash marks that  in QLab is an OSC query. And what that means is
2:56:27
at the time of sending this message go look at  this address find out the value that is there
2:56:37
and replace this token with that value. So what  this message says is set cue T2 color name to the
2:56:48
answer to the question which is what is cue T1 color  name. Then we're going to set this cue to resend 10
2:56:56
frames per second for a really really long time.  So when this cue is running it will continue running
2:57:05
for another hour. And while it's running, it will  constantly watch cue T1 and see what its color is.
2:57:18
Will it
2:57:29
What's happening? That's correct.
2:57:35
No overrides. Why are you not working?
2:57:45
Did I? You're up. You're  up. You're where you belong.
2:57:54
You're where you belong.
2:58:00
Well, we know that worked.
2:58:10
after lunch. All right. Well, this
2:58:20
this is curious. This is irregular.
2:58:28
Ah, there we go. Something something was reset.
2:58:33
So, when I change No, you've got it. That's  actually the answer. It doesn't want a two-word.
2:58:47
So, watch this. Free t-shirt.
2:58:54
Uh if I enclose the if I enclose the query in  hash marks, it will turn the argument into a
2:59:05
string. Nope, that won't work. If I incl... Oh, I  did not type that in the correct I'm not running
2:59:17
the correct um message. Cue T2 color name now  in hash marks. Yeah. So the space in hot pink.
2:59:31
Well done. The space in hot pink breaks the  message because a space separates arguments
2:59:37
in QLab. So now sky blue works also. Hey two  of my favorites actually. Sky blue and hot
2:59:43
pink in here. Um because this message is  constantly running at 10 frames a second.
2:59:50
10 times a second, QLab asks T1, hey, what's  your color? And then sets T2 to that color.
3:00:02
That's interesting. So too  is this version of the one uh of the message where we use a special  operator selected. This says, hey, cue T2,
3:00:14
when this cue is running, whichever cue  is selected, cue T2 becomes that color.
3:00:23
That can be kind of useful.
3:00:32
It also works with name,  right? If this cue is running, cue T2's name is the name of whatever cue is selected.
3:00:46
Notice that when I select all these  cues that have their default name, cue T2 gets nothing because the  default name is not the name.
3:00:54
It's called the default name. It's  got a different different message.
3:01:07
OSC uh reset everything in this list.  including evidently the lights.
3:01:22
Oh, because there's a lighting cue in here.  Um, I can't do that demo because it includes copyrighted material and we are streaming. So,  I'll do a demo like that later if someone wants.
3:01:33
Um the um the OSC query gives you a way to make  messages in QLab that contain information gleaned
3:01:45
from QLab. I don't know that I think that the  recoloring a cue to match whatever cue is selected
3:01:51
is necessarily the most useful thing, but it's  a simple example. Um and I encourage you to
3:01:58
sort of think expansively about it. I use that  for things like um displaying information back
3:02:05
to the human about what's going on right now. Um  um if the if the stage manager has a copy of the
3:02:16
screen showing QLab, I can call their attention to  certain cues by changing their color dynamically
3:02:24
while the cue run while the show runs. Um  I find things like that exceedingly useful.
3:02:30
I've seen people make props that every couple  seconds will change the color of a cue so
3:02:36
that you know that the prop is on the network  and working and online. Nice. Yeah. Cute.
3:02:45
Really cute. Basically, QLab has doesn't have a lot  of facility for just displaying information to the
3:02:53
operator, but what it does have is cues with  names, numbers, and colors. So you can use OSC
3:03:00
messages to use to set the name, number or color,  well not number really, name or color of a cue
3:03:06
that is in the operator's field of view to give  them information. I have one fun example of using
The Voxel's use of long-running Network cues
3:03:13
long running OSC messages that Alec came up with  for this building. Uh because this theater is run
3:03:20
almost entirely by QLab in almost every conceivable  way. Uh we have one particular computer up there
3:03:27
that is the brain of the building and it really  matters if it stops working for some reason and
3:03:33
we need to know and um so Alec came up with this  scheme where he has one computer at the back of
3:03:38
the building which is peri once a second with a  long running infinite network cue sending
3:03:46
a message to the front of the building and if it  gets a message back it says okay it's still alive
3:03:53
uh and it resets a counter somewhere. And if it  doesn't get a message back within a certain amount
3:03:59
of time, it doesn't trip the  switch that says the front of the building
3:04:05
is still alive. And if you know, it's something  like five or six seconds pass and it doesn't hear back. It texts us. It sends us a text message to  both me and Alec to say, I'm very sorry to report
3:04:16
that the QLab machine of the Voxel has crashed.  Please do something about it. So, we periodically
3:04:24
every once in a while get a text message that  tells us that the building has crashed and we need to go do something about it. Uh, and that is  one of my favorite uses of long running network cues
3:04:33
and it just requires one one message a second all  day long every day. The next thing for you to do,
3:04:40
Alec, is to take an Arduino and a solenoid and  bolt it on top of this case so that you can send a
3:04:50
message to the Arduino from home that presses and  holds down on the power button for 10 seconds and
3:04:57
then lets go. Then you can reboot the Mac from a  distance. But of course that said like uh the runs
3:05:10
the building basically doesn't crash. It usually  means out unplug something or some other physical
3:05:17
reality. The internet's down the network is down  or we installed a beta because this is our testing theater. So every once in a while I'll install a  beta of QLab on this machine that's doing as many
3:05:28
things as we can possibly get it to do 24 hours a  day, seven days a week. And if if the beta had a
3:05:33
bug, sometimes we'll find it that way because  it, you know, it's working hard. And I mean, at that point, we almost hope it crashes. Yeah,  exactly. So, it's a it that's uh that's sometimes
3:05:43
a nice thing to see that we got a crash on an  unreleased version and can go fix it. But yeah, it's true. It doesn't um most of the time if  we're not doing heavy heavy changes it it and
3:05:55
uh putting lots of sort of bleeding edge betas  on there. It just sort of sits there all all
3:06:00
week all month just doing just controlling the  building. Yeah. Best practice to restart your
3:06:05
computer with some frequency that I defer to  the experts on. I don't do it. Yeah. You know, it's the support team will tell you do it once a  day and I'm just totally lazy and do it maybe once
3:06:17
a month and they're going to hate that I say that.  Oh, daily reboot. Yeah, I know. You can automate
3:06:22
it. I don't listen to me. What if someone's what  at 4 a.m.? I'm gonna turn the lights off. I mean,
3:06:34
we're also trying to do the worst practices. You  know, we're sort of intentionally doing the bad thing because uh if we can run it for a month  and it doesn't fall over and it doesn't have a
3:06:44
memory leak, that's great. But also, uh it's  it's sort of low stakes here because we know
3:06:50
what's going on. We know it controls. So,  it's better for us to push the envelope and and behave more badly here than we would suggest  that you do. So, that's the other reason. Yeah,
3:06:59
that's that's true. My recommendation to you is  that if you are running a show for a long time
3:07:05
um that wants the Mac to be up 24/7 that I that I  you work some, work out somehow in your process a
3:07:12
once daily reboot. If for no other reason than a  once daily reboot guaranteed will show you whether
3:07:20
something else in your setup has gotten farkakte  and the only reason it's working is because it hasn't been rebooted which is not healthy right.  So if it does, if your if your system can't come
3:07:31
back from a reboot cleanly, that's knowledge worth  having on a you know in a context that is not what
3:07:38
Chris just described about this building. I hope  that that was an a little bit more of networking
3:07:43
that was interesting to you and we can still do  more tomorrow. Yeah. Great. It's 12:05. Um let's
3:07:53
come back at 1:10, 65 minutes, and um we'll talk  about video. Thank you all and thank you Aaron.
Lunch
4:13:16
Hi. Okay, here we are. Welcome back,  folks. I hope that you had a pleasant,
Questions thought of over lunch
4:13:22
restful, and uh nourishing lunch break.  Um we are going to talk this afternoon
4:13:34
about video. Um but as I did before, want to start  by checking if there were any lunchtime musings
4:13:43
that had settled in anyone's mind. Something  you thought about asking or wished you asked or
4:13:48
would like to now ask that came up over your  break. Yeah. Can you target a type? Can you
4:14:00
target a cue type? Does that make sense? Yeah.  I want all my network triggers to be purple.
4:14:07
I don't think so. Okay. I don't think so. I don't  think we categorize cues by type as far as OSC is
4:14:15
concerned. But here's what you can do. In a given  list, uh I'm going to go to network cues. Yeah,
Selecting all cues of a certain type within a cue list
4:14:27
in a given list, you can type shift period,  which gets you the right angle bracket,
4:14:34
which unfolds all groups. Then you can type  command A to select all cues in the list. Then go
4:14:43
to the basics tab and where you were expecting to  see the cue number, you now have a menu telling you
4:14:49
how many cues are selected. And when you click  that menu, you can refine your selection to
4:14:54
only cues of a certain type. And then a message  that is /cue/selected will act upon those cues.
4:15:06
Oh, cheerfully. But I'll do it in a more  complicated list because it'll be even more fun.
4:15:13
In this list, I'm going to start by typing shift period or  right angle bracket uh in the US keyboard. Brits,
4:15:23
French, I'm so sorry. And it will unfold all the  groups in that list. Next, I will type command A,
4:15:33
which selects all cues in that list. Next, in the  basics tab of the inspector, I'll see a menu that
4:15:40
says 166 selected cues. And I can choose from  that list a specific type of cue. In this case,
4:15:49
I will choose fade cue. And now only the  fade cues remain selected and all my other
4:15:56
cues become deselected. At which point I  can run a OSC message send an OSC message
4:16:04
that starts slash cue slash selected and it  will act upon the selected cues which we've
4:16:09
already produced a set of selected cues that  we want and profit. Yeah, splendid. All right,
Video
4:16:24
we're going to talk about video cue cues um and  video in general. And we're going to use this
4:16:30
piece of media which I shot using the world's most  expensive dolly, the New York City subway system.
4:16:35
I clamped my GoPro to the handrail on a northbound  F train and I went across the little stretch of
4:16:44
Brooklyn where the F is above ground before  going underground for a few stops and then going
4:16:49
to Manhattan. And um the reason I used my GoPro is  because at the time that I shot this video, there
4:16:56
was no other easy way to shoot high frame rate  video without spending a lot of money. Um, I don't
4:17:03
live in Brooklyn anymore, so I have to find a new  clever thing to film if I want to replace this
4:17:10
footage. Um, uh, that, you know, I can't use the  subway or I have to make a trip just to recreate
4:17:16
this shot. I'm not sure what I'm going to do yet.  Point is, we're using this shot. It looks a little
4:17:23
fisheye because the GoPro lens is a little fisheye  because GoPros are a little fishy. Um, and we're
4:17:29
going to use this footage to demonstrate some of  the powers of QLab's video um, features. Uh, I'm
4:17:38
going to preface this by saying for humans, so too  for computers, video is harder than audio. Uh, on
4:17:47
the one hand, the lowest sample rate of audio that  most people work at is 44,100 samples per second.
4:17:55
The lowest sample rate of video that people  work with is only 24 frames per second. So you feel like I got to do way less stuff in a second.  But each second, every pixel matters. And so the
4:18:08
computation is harder and the systems of control  are harder because the possibilities are greater
4:18:14
uh in terms of the possibilities of things you  need to tell it what to do about. So, um, if you
4:18:21
don't start off being a video person and you find  any of this vexing, uh, please trust that that is
4:18:27
because it is a little vexing, not because you are  missing something. Um, and we're going to try to,
4:18:32
you know, take our time and go real slow and,  um, learn everything there is bit by bit. But,
4:18:39
as always, stop me, ask questions, ask me to  repeat myself, ask me to slow down, whatever.
4:18:46
Okay. To play video in QLab, you use a video cue,  which is hopefully not that surprising. Video cues
4:18:54
are like audio cues in that their target is a file  on your disk. The file must be a video file or an
4:19:02
image file. We'll talk about formats in a moment,  but to paint to the broadest strokes, any sort
4:19:09
of normal common video file that you easily find,  uh, or normal common image file format is probably
4:19:16
going to work. Um, the video you're going to see  today is mostly ProRes 422 LT or ProRes 422 proxy
4:19:25
and the still images are mostly PNGs and JPEGs.  Others will work too. We'll talk about it shortly.
4:19:32
Um, in the inspector of a video cue, you've  got the basics tab, which we all know about, the triggers tab, which we all know about, the IO  tab, which works a little differently than the IO
Video cues - the I/O tab
4:19:45
tab in audio cues. So, I want to take a moment to  stop and take a moment and look at it. The I/O tab
4:19:52
for video cues will also look different based  upon the type of media that's being targeted.
4:19:58
For example, this video file has no soundtrack. As  a result, there is no audio I/O going on here. But
4:20:08
if I trigger a trigger, if I target a piece  of media that has a soundtrack, we will get
4:20:13
some more options pertinent to sound. We'll talk  about those shortly. To start with though, is the
4:20:19
file target well, which we already know and love  hopefully from audio cues. That's the same. Next
4:20:25
is a listing of the video format of the targeted  video file. This is a ProRes 422 LT file. It's 848
4:20:32
pixels wide by 480 pixels high and it's at 240  frames per second. Over here is a disabled menu
4:20:40
which will become enabled if we use media with  uh sound embedded. We'll talk about that shortly.
4:20:46
Audio format says no audio which is how I can say  so confidently that there's no audio in this file.
4:20:51
Then the video output is the place you choose  where the it's it's analogous to audio output
4:20:58
batch. It is the place where you choose where  the video is going to go. We have a stage
4:21:05
as we call it defined as uh a place video goes  to and that stage separates cues from actual
4:21:16
output devices the same way that an audio patch  separates cues from actual output devices. The
4:21:21
stage is named QClass. The monitor button lets me  bring up a monitor window which allows me to view
4:21:31
the stage on my screen as well as the output.  This can be really useful if for example the
4:21:39
output is behind you and you want to describe it.  Um but in a lot of contexts um the operator wants
4:21:47
to be able to check that they're outputting  but can't see what the audience sees. Uh, the simplest explanation is what happens if you're  using a dowser that physically blocks the path
4:21:57
of light from the projector, but you want to make  sure the signal is good. The monitor window shows you even though the dowser is blocking the actual  light for the audience. It's also a great tool
4:22:07
to use to prove to the house video engineer that  your output really is playing. Now, I am rolling
4:22:14
a cue. I really am. Look, here's the monitor  output. So, it's the problem is downstream.
4:22:22
That's the monitor window. To the right of the  monitor window, uh, are the dimensions of the
4:22:27
stage, just to give you a a clue, and an edit  button to jump you to the video stage editor,
4:22:33
uh, which we'll talk about in time. Yeah, I was  just realizing during one of the breaks, we could take a tour of the live streaming station because  it has a bunch of monitors up and all kinds of fun
4:22:43
stuff that shows this stuff. So, if you want to  look at what is live streaming this class, you
4:22:49
can go look at how we've set that up. Maybe what  we should do is put NDI um scan converter on that
4:22:57
Mac. Capture that whole screen. How many loops  could we do? It'd be amazing. You're very clever,
4:23:05
but you can't fool me. It's turtles all the way  down. Um, that sounds like that sounds like fun,
4:23:11
though, right? Yeah. Yeah. Okay, that's the I/O  tab. If this audio, if this video file had audio,
4:23:19
we would also have an audio output choice down  here, which lets me choose an audio output patch
4:23:25
for the sound in the video file to be sent to.  Again, we'll get there. The geometry tab comes
Video cues - the Geometry tab and fading geometry
4:23:32
next, and the geometry tab is sort of like um the  levels tab for audio is. The geometry tab lets me
4:23:40
choose the basic behavior of the playback of this  video. So to start with, the overarching choice is
4:23:49
mode. Either fill stage mode or custom mode. This  video cue is in fill stage mode. As is this one.
4:24:02
This logo, as you can see here in the sort  of sample view, this logo is a video that is
4:24:08
a square. It is playing to a stage that  is a rectangle. The mode is fill stage,
4:24:14
which means in some way be as big as you can.  Um, there are three styles of fill stage though.
4:24:24
Fit will fit the content of the video to the  stage, the content of the file to the stage,
4:24:32
making it as large as possible while not  exceeding the bounds of the stage in any
4:24:38
dimension and not clipping off any amount of  the video. What that means is since the video
4:24:45
is a square and the stage is a rectangle,  there's blank space on either side of the video. Here you see nothing because QLab is  putting nothing in that in that blank space.
4:24:58
If I switch it to fill, the directive is use as  much of the stage as possible. Clip off some of
4:25:08
the cue if you need to, but don't warp the  shape of the cue. So, this video is still
4:25:15
being shown as a square at its original aspect  ratio. It's just scaled up to occupy the full
4:25:21
space of the stage. And in this case, the top and  bottom get cut off. If I switch it to stretch,
4:25:30
stretch tells the uh cue, display every pixel  of the cue. Use every pixel of the stage,
4:25:37
and if they're not agreeing with each other in  terms of shape, stretch the cue as needed to fit. Yeah. One may be more correct or less  correct for you in any given circumstance.
4:25:53
The other controls in the geometry tab, layer,  geometry, and smooth. We're going to um well,
4:26:01
no, we'll talk about uh we'll talk about layer in  a minute, but we'll talk about opacity right now.
4:26:07
Opacity is a percentage scale from 0 to 100.  Opacity of zero is completely transparent. And
4:26:14
as we fade up the opacity to full 100%, the video  becomes visible. That's how you fade in and out of
4:26:23
video by fading opacity. The little reset button  here resets the opacity to its default posture.
4:26:32
The smooth checkbox, which is checked I think  by default, smooths jaggedy edges in
4:26:41
the video if the video is being dramatically  scaled. So when I uncheck this smooth checkbox,
4:26:48
it's not hugely dramatic in this case, but you  see the jaggedy edges around the white. That's
4:26:54
because this image is being scaled up a great  deal. And the default behavior of anti-aliasing
4:27:02
is enabled by the smooth checkbox. When I uncheck  the checkbox, it gets jagged. And when I check the checkbox, it gets smoothed out. Sometimes you want  the jaggedy look aesthetically on purpose. Um,
4:27:13
we came up with this checkbox when I was working  on a show where I was carefully drawing very low
4:27:19
res sprites which I wanted to be displayed  in a very sort of like 8bit video game vibe.
4:27:26
And QLab was helpfully blurring out  all my jaggedy edges. And I was like, uh, I drew a zombie and I see just a green  wisp. Um, why? And it's anti-aliasing. So,
4:27:39
we added the smooth check box so you can  get the jaggies if you want. Yeah. Um, what kind of anti-aliasing do you use in Chad?  Would you like to answer this one? I don't know.
4:27:54
We'll check the code. Chad, one of our developers,  um, who works on video, among other things,
4:28:00
is fortuitously present for questions of this  sort. Um, it's some kind of nice smoothie pretty
4:28:09
kind is the limits of my knowledge on that. Do you  have a um are you working in a in a situation in
4:28:17
which you have a preference? Um, I I guess there's  I just I'm just curious, I guess, because I know
4:28:25
visual differences between different forms of  anti-aliasing and I'm just wondering what what
4:28:31
form you specifically use. You you you arrived at  a class with curiosity. How dare you? While Chad
4:28:39
is investigating, I will proceed because I want  to talk about the layer um control. So, here are
4:28:54
three video cues. Wasp, Panda, Wall-E, all set to  layer top. The order in which I play them dictates
4:29:06
the order in which they are displayed to you.  When I play the wasp, then I play the panda. The
4:29:12
panda is a larger image. It completely obscures  the wasp. But then this drawing of my favorite
4:29:18
little robot is much smaller. It plays in front  of the panda and therefore you can still see the
4:29:25
panda because the robot is smaller. Right? If  I play these cues in a different order though,
4:29:34
they display in a different order. Their layer  is set to top. Each cue is set to layer top.
4:29:50
But now the wasp is going is  played here with a new cue set to
4:29:55
layer 10. The panda is layer 20.  And I've also scaled it down.
4:30:03
[Baby noises] Hi Elanor. And Wall-E is on layer 30. You can  think about layers as being like a stacking order
4:30:10
where lower layers are farther away from  the audience and higher layers are closer. It is as though the cues have distance  between them. Layer 10 is below layer
4:30:23
20. Layer 20 is below layer 30. And there's  imaginary distance between them. There's no real distance between them. This is a  clever animation. There's a metaphor,
4:30:34
but it's like you have a bunch of index cards  and each one is a cue and they're infinitely thin.
4:30:41
Also, any two cues that have the same layer, the  most recent one is put on top of the previous.
4:30:49
They don't replace each other. If I have  two cues on layer 10, the first cue to play on
4:30:54
layer 10 appears. The second cue to play on  layer 10 appears. If I stop the second cue, the first cue is still there and was all  along. It's like on the fly, QLab says, okay,
4:31:05
layer 10, layer 10 and 1/2, or whatever. The  layers are a stacking order. And the two special
4:31:17
layers, layer top and layer bottom, allow you to  say all new cues that are on layer top will appear
4:31:24
in front of all others. Or layer bottom will  say all new cues appear behind all the others.
4:31:38
When a cue is in custom mode and  not fill stage mode as this one is,
4:31:45
you have your layer control which we  just discussed. You have your opacity and smooth which you just discussed. But  instead of fit, fill and squish, no fit,
4:31:54
fill, and stretch, you have translation,  scale, rotation, anchor, and crop controls.
4:32:04
Translation is left to right movement and up to down movement.  The X-axis is this one. The Y-axis is this one. If
4:32:16
you were like me and you find that difficult to  remember, a wonderful set designer who I know once
4:32:21
was teaching me something in vector works and I  admitted that I had a hard time with which axis is which. And she said x is a cross, right?  And I say sure. She said x is across. And
4:32:34
I have never forgotten it since. So hopefully  if you are like me and have trouble with that,
4:32:39
this will aid you. If you are not like me and  you've never had trouble with it, now you have something to say when someone else has trouble  with it. Um, you can move in X- and Y-axis.
4:32:55
You can also rotate in three dimensions. Rotating  around the X-axis means tipping forward or back.
4:33:03
Rotating around the Y-axis means tipping  left and right. The axis is like an axle that the
4:33:11
thing spins around. Rotating around the  Z-axis which is this one means spinning
4:33:22
Hm? T-axis? What's that one? Oh no no no.
4:33:35
This is the T-axis. And it doesn't there's  no spinning happening here. No, no, no, no,
4:33:43
no. Now, QLab uses a kind of 3D rotation math um  that um produces very smooth movement between
4:33:58
arbitrary rotations. No matter how dramatic they  are, all three of these marks that I've selected,
4:34:06
these just arbitrary 3D positionings, no matter  which I fade between, it always moves smoothly.
4:34:16
If you've ever seen sort of cheaply done stop  um um key frame animation of like figures,
4:34:24
you find sometimes like they're trying to like  move their arms and and it like it looks weird
4:34:29
and choppy. This is the other kind, right? what we  uh the rotation of a cue is represented by a kind of
4:34:42
number or a set of numbers called a quaternion which  is above my pay grade. See aformentioned
4:34:48
notes about Montessori school and selecting  my path through life to avoid doing math. The
4:34:55
metaphor is this. The cue exists inside a ball.  The surface of the ball has a handle on it that
4:35:03
lets you move the cue around. You can twist the  knob and you can move it anywhere you like on the
4:35:12
ball and the cue always stays facing the knob.  Good news is I can get from any orientation to
4:35:20
any other orientation by simply dragging the knob  in a straight line across the ball. Straight from
4:35:27
the perspective of the ball. It is of course  from an outside observer an arc but from the
4:35:32
perspective of on the ball it is a straight line  with or with or without some amount of twisting
4:35:38
the knob. That's the good news. The bad news is if  you want to move a cue more than 180 degrees in any
4:35:48
one direction, the shortest path will be going  the other way. Right? If I want to spin a cue
4:35:55
360 degrees around, the shortest path from here to  here is to not move. My favorite kind. But we have
4:36:09
an option for you. A fade cue can rotate or scale  or translate, right? But a fade cue can also be used
4:36:26
salude to rotate a cue not in 3D orientation  but around a specific axis. And when you use
4:36:35
a single axis, QLab sets aside the quaternions  and just spins the cue some number of degrees
4:36:42
according to your wishes. So, this cue will  rotate the Z around the Z-axis 3600 degrees
4:36:51
or 10 full spins. That's lets you do the "extra  extra read all about it" news animation. Right?
4:37:06
I'd like to point out that when you do that,  you can imagine that the original position
4:37:12
of the cue is like an indexed position at  0 degrees. When you rotate it 3600 degrees,
4:37:22
you've moved the position of the cue from  0 to 3600. If you want to do that again,
4:37:29
another cue to 3600 will do nothing. It's already  at position 3600. If I wanted to do it again,
4:37:41
I would have to make another  cue that sends it to 7200.
4:37:46
Spotlight is my friend. Um, if I  want to send it back to where it was,
4:37:53
I have to rotate it to position  zero. I don't subtract 3600. I don't send it to negative 3600,  right? I just send it to zero.
4:38:05
One of the things that can vex people when using  quaternion rotation is that when you set a position
4:38:14
of a cue in 3D space. To do that, you click on  one of the axis buttons and then drag or you click
4:38:26
and start typing numbers. But when you click  again, the numbers you typed are gone because
4:38:33
these controls are not showing you what is the  current location of the cue according to some
4:38:39
axis. These controls are how much would you like  me to turn the cue in a direction. The actual
4:38:46
position of the cue in 3D space is represented  by a quaternion which is four numbers that I don't
4:38:53
understand. And I challenge anyone to look at four  numbers and tell me and predict the 3D orientation
4:39:00
of the cue. It is not directly obvious. So  what happens here is each time you open up these
4:39:09
controls, you get a box that says how much you  want to go. But when the control is done moving,
4:39:18
that's just the place the cue is in 3D rotation.  And people say, "But Sam, I would like to know
4:39:25
where the cue is." And I say, 'You know where the cue  is? It's right there. Look at it. It's turned kind of like that. And then they say, "Okay, yeah,  but what if I want to make another cue turn just
4:39:35
like this? How can I know?" And I say, "You can  copy this cue's rotation and paste it onto that cue,
4:39:44
but I won't know the numbers." And I said,  "Does the audience know the numbers?" No,
4:39:49
they do not. "Does the cue look nice to  them?" Yes, it does. So, get on with it.
4:39:56
The trouble is expressing the numbers usefully is  challenging. Expressing the numbers productively,
4:40:03
like usefully, no, what am I trying to say?  Expressing the numbers in a way that you can read and make sense of them is not easy to do. So,  instead, we have made a tool here that hopefully
4:40:14
makes it easy to use to actually move the cue  around in space. That's really my whole point.
4:40:26
Relative cues of course exist. Uh,  and I want to show a scale change
4:40:32
that is relative. I've made this  cue relative. And the scale is 1.1.
4:40:39
When I every time I hit this cue, I  get a 10% increase in size, right?
4:40:47
because it's multiplicative. 1.1  times the scale is 10% larger than it was before. Every time I hit  this 0.9 cue, it reduces by 10%.
4:41:02
Relative rotation also works, but I'm  here to tell you it's not what you expect.
4:41:11
Every time you hit a 3D rotation that is relative,
4:41:18
it the math is right, but the behavior feels  weird. And getting it done backwards. Like
4:41:26
you'd think, all right, if I just go one,  two, three, four times uh in one direction,
4:41:38
I should be able to just get it back to where  it was by going one, two, three, four times back the other direction. But the answer is no,  you cannot because quaternion math is hard.
4:41:48
All I am want to say is that quaternion math  is hard and relative rotations is hard and
4:41:54
doing them both is hard and if it looks good  it is good and if it doesn't look good keep changing it till you do like how it looks and then  you've done it right and um we try to give you as
4:42:06
many tools as possible. Single axis rotation  is very predictable. One, two, three, four,
4:42:16
five. Six spins in one direction. Then I take the  exact same axis and spin the opposite way. One,
4:42:22
two, three, four, five. And it's right back where  it was. So single axis fades with relative math
4:42:29
quite logical. But the reason that the other one  is not quite logical is because math is hard.
4:42:44
Now, all the cues we've been looking at so far  that have been rotating and moving have been
4:42:49
using the center of the cue as the origin of  the cue. And that's an unusual thing for QLab
4:42:59
to do. Many other video tools choose the lower  left corner as the origin. I would say that's
4:43:04
probably the most common. Some use the upper left.  Apple in their infinite wisdom uses the lower left
4:43:10
sometimes, the upper left sometimes depending.  And do they tell you when they use which? No, they do not. QLab uses the center of a cue as  its origin because that is the way that we feel
4:43:22
you can get the most predictable behavior when  you have an arbitrary size stage on which you
4:43:28
can play arbitrary sized cues. If you want to  just throw up a bunch of images, they all align
4:43:35
center to center. That's nice and easy. Uh,  if you had them all align lower left corner
4:43:41
to lower left corner, your eye would be jumping  around more as each cue played. Of course,
4:43:47
you can move anything the way you want it, but we  feel that the center aligned default provides the
4:43:53
most sort of straightforward and predictable  behavior. But if you have a door and you want
4:44:01
to open it by using a Y-axis rotation, it looks  weird because it pivots around its center point.
4:44:12
But the anchor parameter lets you move this little  blue plus from the center of the cue to some
4:44:19
other place and then that becomes the center  of the cue as far as fades are concerned.
4:44:25
So, by putting the anchor aligned with the  left edge of the door where the hinges go.
4:44:35
Not so bad.
Video cues - the Video FX tab (and, briefly, the Time & Loops tab)
4:44:45
Video effects. We have them. End of lesson. Uh,  no, not true. Um, the next we I'm glossing over
4:44:55
the time and loops tab. And the reason I'm  glossing over it is you've already learned everything there is to know about it when we  talked about audio. Uh, everything you can
4:45:04
do in an audio cue, you can also do in a video  cue. Slicing, looping, vamping, devamping. But
4:45:10
let me tell you, it's a little tricky to do that  in a video cue that has no audio track because
4:45:16
there's nothing you can see here to work on, which  is why for many reasons, this is the least of
4:45:21
them. I encourage you to put by default an audio  track in all of your video cues. If it's silence,
4:45:29
that's fine. If it's a metronome, that's even  better. Just something so that you can count
4:45:34
your regular units of time and just make it easier  to work with this tool visually. So, I that's the
4:45:42
time and loops tab. The video effects tab is a lot  like the audio effects tab for audio cues. We're
4:45:49
going to talk about blend mode separately, but  it lets you add a video effect the same way audio
4:45:54
cues let you add an a add an audio effect. The  difference is there is no audio unit equivalent
4:46:00
for video effects. There are a lot of um video  format video effect formats that aspire to be like
4:46:09
the audio unit, but nothing has really clicked.  There is no universally functional video effect
4:46:15
plug-in format. So all these effects that we have  here were made for QLab specifically and are built
4:46:24
into QLab. This selection of video effects expands  upon the QLab 4 list of video effects greatly, but
4:46:33
omits one essential video effect that we used to  have in four, which I want to talk about briefly,
4:46:38
which is use your own. QLab 4 used a kind of um uh  an underlying video technology called Quartz. And
4:46:47
Apple had a program that they made and let people  download called Quartz Composer which allowed you
4:46:53
to produce your own video effects in the Quartz  video rendering system. And Quartz Composer
4:46:59
is super cool and Apple killed it. And Apple  stopped using Quartz and we stopped using quartz.
4:47:06
QLab 5 uses Metal, which is Apple's newer video  toolbox, which is much better performing and much
4:47:14
more capable, but it has some limits, and one  of them is no quartz composer or no no Quartz
4:47:19
Composer equivalent. But we did some triage of all  the times that people talked to us in QLab 4 about
4:47:28
video effects and we've determined that this list  of effects that we have now plus the addition of
4:47:35
blend modes plus the addition of a feature which  I'm just about to describe covers we think the
4:47:42
vast majority of situations in which a person  chose to use their own effect that they made
4:47:48
in Quartz Composer. So, while this is technically  the removal of a feature, it feels probable that
4:47:56
the total result is you're basically still going  to be able to do what you were able to do before. If that's not true, let us know because we're  eager to make sure that we can cover all those use
4:48:06
cases. We just can't cover it with Quartz Composer  because Quartz Composer doesn't work anymore. And that's on Apple, not on us. Um, and I mean for  good reason. It was old. It was time to time
4:48:17
to move on to a new and more powerful thing. Um,  this video cue is playing with a hexagonal pixelate
4:48:24
effect. Um, and um, fade cues can target  video effects and change their parameters,
4:48:41
which can be a little trippy on the  eyes with this particular effect.
4:48:47
The thing I said I was about to talk about in  a moment, which is a new feature that QLab 5 has that enables you to do things that QLab 4 didn't,  is um you can also put multiple video effects on
4:49:01
a cue. So, this has a crystallize effect, but now  I'm going to fade in a zoom blur on top of that.
4:49:08
Here we have two video effects, crystallize and  pointillize, and zoom blur. And the order matters.
4:49:16
So, this effect is getting crystallized, then  it's getting zoom blurred. If I drag them into a different order, now it's getting zoom blurred,  and then crystallized. This is what happens when
4:49:25
you spin around the [Laughter] Yeah, I do not like  it. I'm going back to the other. That feels safer.
4:49:38
Um, you can add as many video  effects to a cue as you like. You are limited only by your  computer's processing power.
An aside about Apple Silicon (it is impressive)
4:49:47
I just heard the fan
4:49:53
turn on. That's exciting.
4:50:00
Well, I was covering the vent hole and rendering video effects at the same time. If I  stop the cue, will you settle down?
4:50:10
No, doesn't matter. It's running just fine. I  think it's it's notable that that was surprising
4:50:16
to Sam, right? I mean, that this is we're not  used in the olden days. I mean, Sam will talk
4:50:24
about this more, but in the olden days, having  fans running loudly and often was was common. And
4:50:31
with Apple silicon and the newer machines and with  metal and with the new rendering engine in QLab 5,
4:50:37
it is much less common. Yeah. The show that I  learned that the French keyboard is a hassle in
4:50:44
QLab was uh a video mapping installation that I  helped develop um in a castle in Provence. And
4:50:55
this installation was being um was leveraging a a  law that is true in France, which is they've got
4:51:02
so many castles lying around that if you buy one  and renovate it into something that is available
4:51:11
to the public in any form and which celebrates or  showcases or demonstrates the history or culture
4:51:19
that that castle is a part of, the government of  France will foot your bill 50%. They'll go halvsies
4:51:26
with you. So, a gentleman who it turns out is the  sixth richest man in France bought this castle,
4:51:34
uh, immediately spent the exact same amount of  money he spent buying it, repairing it to meet
4:51:41
modern seismic code, and then began developing  it into a themed attraction, which told the
4:51:47
history of this particular castle and the uh,  eccentric individual who owned it, who was a minor
4:51:57
naval hero for France. Um most notable uh and  this is why he was so popular in France. His most
4:52:06
notable thing was that he was captured by the  British Navy, imprisoned, and he escaped prison,
4:52:14
stole a boat and sailed back to France and  then turned around and sunk some British ships.
4:52:20
And like as far as I can understand it, that is  kind of the pinnacle of French victory is like
4:52:27
something bad happened to me. I not only solved it  but stuck it to the Brits uh in in the solution,
4:52:35
which it really seems to me is the thing that  makes them the most excited. And I can I can get behind that. Um uh the British Navy is a bully.  Uh and this castle was owned by this guy. And so
4:52:48
you go through the castle and you see the story of  the guy going to sea and getting shipwrecked. And
4:52:54
there's like one room you go in, it's like the  edge of a ship is there and it's like pouring water and there's all this thunder and lightning  all around and you hear, I'm told because I can't
4:53:05
speak French, you hear voices saying like, "Oh  no, we're being shipwrecked. Look out, there's the British Navy. Oh no, we're screwed." And then  in the next the next room is like, "And then he
4:53:15
was in prison." And it's like a little prison and  you can see the shadow of the guy pacing back and forth behind a a prison wall. It's very very cool  installation. The part I was supposed to do was
4:53:25
called the "voute" which means "vault" which is a long  hallway very damp. Uh the ceiling was very damp.
4:53:32
The floor was very dry and very dusty. And  the hallway was lined with 16 HD projectors.
4:53:41
uh wait eight, yeah 16 HD projectors and a uh going  the length of it then a pair of HD projectors
4:53:50
mapping the end of the wall and then inset in  a window was a 4K 60-inch television built
4:53:55
in architecturally to a fake window as though  it's the air outside the window and driving all of
4:54:02
these projectors that they wanted one animation to  play throughout the whole thing and you walk into
4:54:07
the voute and then as you walk through it's the  story of the "batisseurs" which are the monks who built
4:54:12
the castle out of raw monk stuff or I don't know  what rocks probably presumably. Yeah, I I assume.
4:54:21
But special special French rocks from Provence.  Um and um so you walk in and the animation is,
4:54:31
you know, it's like 30 feet long and 16 feet high  and it's the ceiling is arched. So, all of these
4:54:38
video projectors are overlapping enough that you  can create a blended single image. And driving
4:54:44
this thing were two Mac Pros, 2019 Mac Pros, fully  loaded double video cards in each. Uh, each cost
4:54:53
€35,000. Uh, plus the projectors. So, just the Macs,  €35,000 a piece. So, I'm sitting in front of €7,000
4:55:02
worth of video projection power. This thing.  Well, no, that's not true. The last time I did
4:55:08
this class, I had a Mac Studio here, the M1 Ultra  Mac Studio. That M1 Ultra Mac Studio cost $8,500,
4:55:15
and it would absolutely outperform the $70,000  worth of Intel Mac Pro. The degree to which the
4:55:23
Apple silicon processor is more capable for a  variety of tasks, including those which QLab are
4:55:30
most regularly engage in, cannot be overstated.  It is stupidly better. It is wildly better. Um,
4:55:39
and so had had they chosen to do a refresh at any  time now, I if they if they choose to do that,
4:55:46
I would go in there and replace two huge  rack mounted fans screaming. They had an air conditioner ducted straight into the v the vent  hole on the rack where the two Mac Pros were. Um,
4:55:57
through like three layers of filtration because  everything is covered in what I called "voute dust." I don't know what it actually was, but it was  awful. Um, uh, no, just get rid of that. Give me
4:56:08
one of these. It's this big. End of story. Okay.  Point is, when I would run this effect on the Mac
4:56:17
Pro, the fan would go from loud to excruciating.  When I'm running it on the M4, is this an M4 and
4:56:26
M4 Pro? But there's three Blackmagic cards  in there. Yeah. Yeah. So M4 vanilla here up
4:56:33
until this Mac Mini. Yeah. So this is Apple's  entry-level Mac. It cost 600 bucks. The fan was
4:56:41
not running at all and it went and it's already  quieted down now that I've shut off that cue. So
4:56:50
it goes from no fan or inaudible to running this  cue. And I'm like, I can kind of hear a fan.
4:57:00
You put it under your desk or in a rack backstage.  End of story. No problem. But the zoom blur is the
4:57:07
secret weapon. If you want to find out whether you  have a computer that can can hold its own or not,
4:57:14
throw a couple of zoom blurs at it. For whatever  reason, that really grinds their gears. I'm sorry.
4:57:24
Thank you. I thought you said a I thought  you said a word in French that maybe I was hoping was zoom blur in French. Yeah,  I also don't got no French. Okay,
4:57:35
so that's multiple effects. Yes,  Alec. Now that we're in video world, would it be worth touching on always audition so  people can fly around? That's a good idea. Okay.
4:57:50
Um, I'm thinking of um an Eddie Izzard bit  about when she did a she did a stand-up act
4:57:58
in Great Britain that she had done in America  and she did something very very English and everyone laughed and then she said, "Did you  change that bit when you did America?" Nope.
4:58:08
Left it the same. Couldn't care. And then uh  and then she did another bit where I was like, "And does that come after that? Was there a  connecty bit? Did you write a connecty bit?"
4:58:15
"Nope. No connecty bit. And so right now, no  connecty bit. We're just going to jump to a completely different topic briefly. No connecty  bit. But once we finish this topic, you with
A brief aside about Always Audition
4:58:26
Max there will be able to play video on your  screen without taking over your screen. No, you
4:58:34
know what? I'm not even going to do it fully. I'm  just going to do this. For those of you who want to play video on your Mac right now, please to go  to tools menu and choose turn on always audition.
4:58:45
When you do that, your go button will become an  audition button. When you play video with the
4:58:50
audition button, instead of with the go button, it  appears in its own separate window. There's good
4:58:59
interesting stuff to teach you about that, which  I will I promise later. But for now, you just have this window that you can look at video in in  your own screen without obliterating everything
4:59:08
else you're looking at. Does everyone who want  to understand that understand it sufficiently?
4:59:14
Okay, great. And then more teaching about  this topic later. Thank you, Alec. Yeah,
Answering an earlier question about smoothing
4:59:24
I'll answer the earlier question. Oh, great. I was  looking for a good spot where you would be paused,
4:59:30
but uh the answer to if you check the smooth box  there, what kind of smoothing is that doing? It's
4:59:36
doing bilinear interpolation. Which,  if you're selecting between different options
4:59:42
for making things smooth, is on the very fast  to do which is why it's our default thing to do
4:59:48
um but not the prettiest of everything. Uh we've  never gotten a complaint. We could easily add other stuff like bicubic and Lanczos if that's  how that's pronounced. I don't know how that's
4:59:57
pronounced. Um we can add other options but  bilinear seems to have been enough for most people. People don't seem to complain so we  haven't bothered to add it. So if you have a
5:00:05
problem and if you want something different  write us and tell us and we'll add a issue.
5:00:10
Neat. Bilinear by cubic and what's the other  one? Lanczos. Lanczos. I'm not sure. I'm not
5:00:17
sure how to pronounce it. I've seen that word  and also wondered how to pronounce it. Um yeah, we could add those. We just haven't done it.  Cool. Does bilinear interpolation suit your needs?
5:00:31
I work for a university theater department.  So, yes. So, yeah. Okay, great. Excellent. Um,
5:00:42
thank you for that, Chad. I appreciate it. I also  wondered but never thought to ask. All right, the
Video blend modes
5:00:50
next thing I want to talk about is the blend mode  uh menu here in the effects tab of video cues.
5:00:58
Here's a video cue, that same video cue that  I was playing before. And now I'm going to
5:01:06
uh it's playing on layer 1. Here is a video cue,  an overhead shot of the ocean. It is playing on
5:01:13
layer two. But this video cue is  playing with a blend mode of difference.
5:01:24
the blend mode of a video signal. What that  means is how does that signal composite or
5:01:33
add up or combine with the video signal that is  below it in terms of layers. Right? The default
5:01:44
behavior of QLab, a normal blend mode,  is a fully opaque video cue on a higher
5:01:50
layer will completely obscure a video cue on a  lower layer, which is like how real objects
5:01:55
work in actual space. And so that's fairly easy  to understand. If I have an image and then an
5:02:04
image and this image is completely opaque, this  image becomes completely invisible. But because
5:02:11
I have a lot of light here and this paper  is kind of thin. If I hold them properly
5:02:20
now, this is harder. This is  easier for me to see than for you. You can kind of make out. You  know what? Here we go. Here we go.
5:02:33
I'm going to put them in front of a Go  over there. In front of a bright thing.
5:02:42
the what's behind shines through, right? It means the thing on top is  not fully opaque. That is blend mode.
5:02:54
A cue's opacity is on a scale  of 0 to 100%. And that means
5:03:02
actual opacity assuming a normal blend mode. But
5:03:09
because we have multiple blend  modes available, different uh effects can be achieved. This is a part of  QLab uh that is a little bit difficult for me
5:03:21
because I have found the names of blend modes and  we use fairly standard names for blend modes. Um,
5:03:29
I find the name of blend modes almost  impossible to latch on to for reasons that
5:03:35
uh maybe a psychologist can interpret. I just  can't latch on to what these words mean. So,
5:03:44
here in the doc under video blend modes,  I have a series of textual explanations.
5:03:54
The darken blend mode creates pixels made of the  darkest value from each channel. That means the
5:03:59
lower layer and the higher layer. Uh oh no each  channel of each source pixel. So red channel,
5:04:05
green channel, blue channel. The multiply  creates pixels by multiplying channel values together. Blah blah blah blah blah. What  I've done here is basically made that demo
5:04:15
and then made little animations of each  version of their com compositing using
5:04:22
each blend mode. I've scoured the internet  and found like I found every definition of
5:04:30
the overlay blend mode that I could find and I  kept reading them until one of them made more
5:04:35
sense than the others and then I rewrote that  one in hopefully even the clearer language.
5:04:41
So, I did all this homework. So, then made  all these little thumbnails. And the truth is, even after doing that, I still can't keep track  of them. So, for me, for this guy, the way I do is
5:04:50
I always just either refer to this page or click  through blend modes until I like what I'm looking
5:04:56
at. But between blend modes, multiple video  effects, and um the increased power of modern Macs
5:05:10
running the more efficient video engine based on  metal in QLab 5, the number of different looks that
5:05:18
you can achieve in QLab is dramatically increased.  So um this is an area which I think really profits
5:05:27
from enthusiastic experimentation. So I  encourage you to grab video material. Um I use
5:05:36
um you can if if you don't have access to a  lot of video material. Well, first of all, anything you shoot with your phone will  work nicely, but second of all, Pond Five
5:05:46
uh is a relatively affordable stock video uh site,  and they offer low res downloads of all of their
5:05:56
material. It's just got a watermark and has a guy  saying Bond Five every 15 seconds, which is kind
5:06:04
of irritating. Um, but if you just need to like  get some video to work with, that's a great way to go. Um, I don't have any recommendation like uh  freesound.org for video. freesound.org is my my
5:06:18
go-to recommendation for free sounds. Um, Pexels,  Pexels, is another resource. Do they have a good
5:06:26
free library? They have a great video library.  Oh, both these are from Pixels, but I bought them because they seemed well priced and they  looked really nice and I was looking for something
5:06:34
specific. I didn't know they have free stuff.  Pexels. P E X E L S. Pixabay? Okay! Um, something
5:06:43
that you should not do is just rip stuff off of  YouTube because that's someone's property. Um,
5:06:50
YouTube's default posture is that the copyright  for the video belongs to the person who posted the
5:06:56
video, and just pulling something off of YouTube  and playing it is not uh legal. Yeah, YouTube does
5:07:03
however have a pretty fat library of free to use  music and sound effects. I'm glad to hear that. If
5:07:10
you go if you go into just like YouTube studio,  like you have an account anytime you like the
5:07:16
YouTube studio section of the site. Yeah. Down in  the bottom there's like a big sound library there
5:07:21
all the time. Cool. Very cool. Um, and if you're  looking for um um paid, you know, paid to use
5:07:36
the thing you're looking for, the rights that  you're looking for are complicated for video, right? Because most video clip sale websites  assume you're going to use the clip either for
5:07:45
broadcast or for distribution like on a DVD or for  download or for use embedded on a website. It's
5:07:53
very difficult to find a set of rights that in  explicitly include live playback in a theater. So
5:08:00
you have to sort of read between the lines and try  to figure out what is the most appropriate source or as much as possible shoot your own footage  or um use stock footage that is royalty-free and
5:08:14
usable sort of un in an unencumbered way.  Um but that's a topic for another class.
5:08:26
Another um the other the last setting  on the geometry tab which we haven't
Video crop controls (and the shutter and window effects)
5:08:31
yet talked about is the crop setting.  I'm going to just play our FRA here.
5:08:41
The crop Oh, baby girl. The crop control  here, which is not addressable with a fade cue,
5:08:49
is sort of like the trim tab for audio.  Crop lets you crop in the video effect,
5:08:55
uh, the video material. So, if you're trying  to use only a subset of the pixels in a cue,
5:09:06
it's also kind of analogous to the start time and end time. It's just spatial  instead of temporal, right?
5:09:17
These um these controls which again can't be  faded also exist in the video effects tab as
5:09:28
uh shuttering or windowing which are two different  ways to solve the same problem. These are fade-able.
5:09:35
So, if you want to adjust the crop of a  of a cue dynamically using a fade cue,
5:09:40
don't use the built-in crop control, use  the video effect, either shutter or window.
5:09:49
I want to talk about why they're different.
5:09:55
Hang on. I want to talk about  why and how they're different.
5:10:04
That cue is cropped using the unfade-able  crop controls, right? The one farthest
5:10:10
to my right. This cue is shuttered. Both  of them have a zoom blur, but the cropped cue,
5:10:18
the boundaries of the cue are brought in by the  crop, and the zoom blur can't extend past.
5:10:26
The zoom blur causes the number of pixels  that a cue wants to use to be greater
5:10:31
than the original number of pixels because  it's blurring outward. But the crop is an absolute non-negotiable final limit to the  number of pixels being used by the source cue.
5:10:43
So when you crop, it is always a final step.  But a cue that is using the shutter effect
5:10:53
can have that shutter effect render before  the zoom blur. And so the zoom blur can
5:10:58
exceed the bounds of the shutter. Right? I  could also reorder it and put the shutter
5:11:05
afterwards and then pull the shutters in  to simulate exactly the uh crop effect.
5:11:23
Well, not exactly, but you get the idea, right?
5:11:29
So that's the essential difference  between crop and shutter. Shutter,
5:11:34
the difference between shutter and  window is simply one of nomenclature.
5:11:41
Window lets you set a width and a height for the  cue and an origin x and y point for the window
5:11:52
to be uh anchored in. So right now it's anchored  in the lower left corner and we're shuttering
5:11:59
uh in from one side and in from the top.  That's window. Shutter is a left, right,
5:12:06
top, bottom control. And interesting to me a  feather effect. When feather goes all the way,
5:12:14
it gets rounder. When feather goes  to zero, it stays rectangular.
5:12:22
I'm sorry. Not that's not true. I made a  mistake. I misspoke. Feather softens the edges of the shuttering. Separate question is  rectangle or ellipse. I can make it elliptical
5:12:36
or I can make it rectangular and I can make it  hard edged or soft edged using these controls.
5:12:49
Okay, that is a quick summary of the total list  of the powers of the video cue. Understanding
5:13:00
that a video cue which has audio track in it  has some additional powers because it has audio.
5:13:06
You've already learned almost all of the  things that there are to say about audio,
5:13:13
but I just realized that I'm not sure I have  a video on here that has a soundtrack. Yes,
5:13:25
here we go. There is. I thought ahead.
Video cue targets with audio tracks
5:13:32
Um, we're going to go all the way back to the  I/O tab. Now that we have this audio cue here,
5:13:41
this video cue here that's  targeting a piece of media that has an audio track. In fact,  it has more than one audio track.
5:13:53
This menu, the audio format menu, appears when  your target video file has at least one audio
5:14:01
track. And now we have to have an excruciatingly  pedantic discussion about the difference between tracks and channels. These are things that are  used pretty interchangeably by a lot of people,
5:14:12
but folks who make vinyl records do not use  them interchangeably. Right? The record has
5:14:18
two channels, but each song is its own track.  CD has two channels, but each song is its own
5:14:25
track. In the world of digital video, a video  file can have any number of tracks. Each track
5:14:38
can have up to 16 channels. So when you pop a  DVD in a DVD player or a Blu-ray in a Blu-ray
5:14:47
player for a commercially made film, you can  choose your audio track. Is it the full surround
5:14:57
stereo the full surround mix as originally made  by released by the filmmaker? Is it the full
5:15:07
surround version dubbed into another language?  Is it a stereo mixdown because you don't have
5:15:13
surround speakers at home? You have just two  little stereo speakers or the speakers built in your TV. Is it a closed caption track? Blah  blah blah blah blah. So each track can have some
5:15:25
number of channels. The channels refer to the  number of speakers. So, the surround channels,
5:15:32
I'm sorry, the the surround track might have left,  center, right, sub, left surround, right surround
5:15:40
or the stereo version might just have  two channels, left and right. Yeah,
5:15:46
QLab 5 supports you using any one track of  a video file at a time. And then once you
5:15:56
choose which track you're using, QLab can use all  the channels in that track. Since the limit of
5:16:03
channels in a track is 16 and QLab's limit of  channels in a cue is 24, which is greater,
5:16:09
we're always ready to rock with all of the  channels that happen to be there. So here
5:16:15
in audio format, I see we have two uh two tracks  available. One is an MEG 4 AAC channel. I'm sorry,
5:16:25
track that is labeled as being in English with  two channels in a stereo configuration at 48 kHz.
5:16:33
The other is an AC3 encoded audio track. That's a  Dolby audio format, also in English, two channels,
5:16:41
stereo, left, right, 48 kHz. So, I pick the one  I want and then that's the audio that gets played
5:16:49
when the video cue plays. Since there is an audio  track, at least one audio track in the cue in
5:16:58
the target file, I'm also given the opportunity  to choose an audio output patch to use. Salute.
5:17:08
I'm also given this option here, follow  video clock or follow audio clock. And
5:17:14
here we're going to draw upon our earlier  clock discussion. When a video cube plays,
5:17:22
how often should it update itself? Well,  if it's 24 frames per second video cue,
5:17:31
we'd like to update it 24 frames per second. But  if it's a 24 second video cube playing on a 60
5:17:36
frames per second screen, I guess we should update  it 60 times a second, right? Because the screen is
5:17:42
updating 60 times a second. But what if it's a  video cue that's playing on two screens at once
5:17:48
and one is 60 frames per second and one is 30.  Okay, now it's got an audio track. The audio track
5:17:55
is playing to an audio device that's updating  at 4,000 48,000 times per second. Which of these
5:18:01
clocks is going to be the clock that drives the  playback of the video cue? And it used to be
5:18:07
that QLab's policy was a video cue that has no audio  track updates according to the clock of the video
5:18:16
device it plays to. If it's playing to multiple  video devices, it chooses one of those two.
5:18:24
If the video cue has an audio track, then it follows  the clock of the audio device. Okay. But then we
5:18:34
run into problems where if the audio clock and the  video clock which cannot talk to each other have
5:18:43
um a disagreement about when the edge of one frame  should stop and the beginning the and the next
5:18:51
frame should begin. If we are following the no  let me say it this way this is hard. Let's imagine
5:19:02
that we travel through time slower. So that 24  frames per second looks like this. And we can see
5:19:10
each frame coming on lasting for some time then  coming out. So each frame is like a chunk of time,
5:19:16
right? If the if QLab is supplying frames according  to the tempo of the screen that's displaying it,
5:19:25
the screen can be like I'm updating at this tempo.  Give me a new frame. And now a new frame. And now
5:19:31
a new frame. And so the the synchronization of  each frame coming out of the video file and each
5:19:38
refresh of the screen will be perfect because the  screen is in charge of asking for the new frame.
5:19:45
But if the video cue is following the audio  devices clock, which goes way faster, right?
5:19:53
44,100 times per second instead of 24 or even  faster. Usually it's great. New frame, new frame,
5:20:00
new frame, new frame, new frame. No problem. Here  you go. Here you go. Here you go. But what if it
5:20:06
doesn't line up mathematically so that the screen  is asking for a new frame at this exact moment and
5:20:13
the audio device is ready to give you a frame  at that exact moment. What if the audio device wants to give you a frame very slightly later? You  will get a momentary visual glitch in your video
5:20:26
playback. Even if you have a very fast Mac, even  if you have a very high quality screen, even if
5:20:31
you have a very well-put together video file, you  will have these momentary glitches if the playback
5:20:37
of the video file follows the audio devices clock  and the audio devices clock and the video devices
5:20:46
clock are not in direct communication, which  they usually aren't. So, we allow you to choose
5:20:57
Is this cue going to follow the video clock and  allow for the fact that it's plausible that every now and then there'll be an audio glitch which  uh sound like a little pop which is the exact
5:21:10
same problem happening on the audio side that I  was describing on the video side or we going to have it follow the audio clock and allow for the  possibility of a small video glitch every now and
5:21:18
then. Unless your clocks are synced together in  hardware, unless you have your video device and
5:21:24
your audio device having an external clock sync,  you're going to have to choose one or the other.
5:21:31
So rather than make that choice for you, we let  you choose. And you can decide, well, I'm doing a
5:21:39
show in a context where a very small visual glitch  will be eye-catching, but a one sample glitch out
5:21:46
of 48,000 samples per second is unlikely to be  caught because I'm playing some mushy, floppy,
5:21:53
Brian Eno, ambient, who knows what, and a little  glitch is going to be very difficult to catch.
5:22:00
Or you could say, I'm actually playing um a  meticulously recorded classical orchestral
5:22:06
piece and a minute glitch is going to be very very  noticeable and my video is some very mushy smoogy
5:22:13
stuff and a small glitch will not be noticed. So  I can make that choice on my own uh and allow for
5:22:20
the possibility of a slight glitch on one side  or the other according to my design choices.
5:22:25
to add a little a little deeper dive into that  answer. It's almost always safe to have the video
5:22:33
clock to follow the video clock because most of  the time the quote unquote problem you're going to
5:22:39
hit is is less likely to be a glitch or a dropped  frame of audio because the nice thing about audio
5:22:45
is you can stretch it. You can sort of speed it up  and slow it down in small amounts and not notice that. And so we are able to do that. So if we're  following the video clock, which we do by default,
5:22:56
and the it is technically true that the audio is  not playing back exactly the same way it would
5:23:02
if it's following the audio clock, but usually  the way it changes is that we have to just do a tiny amount of speed up or slow down here and  there that you actually can't hear. Right? If we
5:23:12
play back a 48,000 uh sample per second track for  3/4 of a second, we play it back at 48,01 samples
5:23:21
per second, you won't hear that difference, right?  So, in most cases, if you follow the video clock,
5:23:28
that's what you want because the video  will be perfect. The audio will be, as far as you can tell, perfect, and you move on  with your life. So, that's that's 99% of the time
5:23:39
that's what you want. Um the the the other 1%  of the time is you really care about how fast
5:23:47
the audio clock is going over a long period of  time. You're trying to synchronize a video to an audio track that runs for a very long time and  those two clocks would be drifting otherwise like
5:23:58
a movie that runs for two hours. And you don't  care about maybe one or two dropped video frames,
5:24:03
but you definitely don't want the audio of the  actor speaking in it to drift away from the video
5:24:09
that they're seeing. Those kinds of things. Yeah.  Yeah. Ale had a project recently where I needed to
5:24:16
play four 4K videos that are 10 minutes long at  exactly the same rate. Like play four videos to
5:24:23
four projectors for I could have solved it other  way, but it had to be done this way. And I needed
5:24:29
to set them to follow audio clock for those videos  to be in perfect frame sync with each other over that long duration. Right? Because your four  projectors had no genlock port. So you couldn't
5:24:39
genlock the projectors together, right? There  was a SDI multi multi there was an FX4 SDI in
5:24:49
the middle. So theoretically I was using it video  clock but yet they would drift. Yeah. So one thing
5:24:57
that's nice is when multiple video cues well when  multiple cues of any kind are playing to the same
5:25:02
audio device that audio devices clock is what's  driving them. So any cues which are playing to the
5:25:09
same audio device will stay clocked alike. If that  clock goes off the rails, all the cues go off the
5:25:14
rails together with it, but they are together.  So Alec had four cues playing. All four cues are
5:25:22
visually playing on different devices. But since  they all had an audio track and the audio track was all assigned to the same device, that device's  clock was in charge and they stayed in sync,
5:25:32
which includes being wrong together if the  clock is wrong. But at least it's together.
5:25:39
Yeah. Okay, great. Um, what did I want to say  about audio? No, all all I wanted to point
5:25:48
out is that here we are with the levels tab,  the objects tab, and the audio the trim tab,
5:25:56
and the audio effects tab all available to this  video cue because this video cue has an audio
5:26:01
track and we're using that audio track. And an a  video cue that has a video with audio in it is kind
5:26:10
of like a video cue with a built-in audio cue.  So everything that happens in audio land can
5:26:16
happen to a video cue that has an audio track. All  the things you learned yesterday are pertinent. Yeah. Great. So we've been assigning these videos  to this stage and displaying it here. And I want
Workspace Settings - Video
5:26:30
to talk about the video stage editor now, which  is unquestionably the most complicated part of
5:26:36
QLab. So, we're just going to take a moment to  appreciate that. And now we're going to dive
5:26:43
into it. I mean it so much that I'm hiding other  windows. Okay, here we are in workspace settings.
5:26:52
There are four tabs: video outputs, output  routing, output devices, and video inputs.
5:27:03
Friends, I'm going to go backwards across this  list from right to left. Not because it's in
5:27:09
Hebrew, not because it's in Arabic, because I have  tried teaching this both ways. And either way,
5:27:17
you have to assume that you know something I  haven't taught yet before it will all make sense.
5:27:24
But by going backwards, there are the fewest  number of those things. So we go backwards.
Video Inputs
5:27:30
The video inputs tab is the simplest. It has  nothing to do with output. It's input only. The
5:27:36
video inputs tab lets you create a patch that you  will use to bring live video into QLab. Just like
5:27:43
uh an audio input patch lets you bring live  audio into QLab. You can name your patches
5:27:49
and you can choose any video device that is  available. QLab accepts USB connected webcams.
5:27:59
Blackmagic Designs video devices. Um, Blackmagic  Designs is a Australian company. They make groovy
5:28:07
video hardware that is relatively affordable.  We get asked all the time, will you support AJA
5:28:13
hardware? And the answer is, we'd like to, but  AJA makes it difficult. So, it's on the list,
5:28:19
but it's not high on the list until AJA makes our  lives a little easier. The last conversation we had with them about it made it seem like they're  going to make our lives a little easier. So,
5:28:27
the next time we dig into video input is the most  likely time to see a change there. Hopefully,
5:28:33
we will. We also accept video into QLab using  NDI, which is a network video um protocol,
5:28:40
kind of like Dante for video, which is not Dante  for video, which also exists, which is a hassle.
5:28:46
And then we also accept video over Syphon which is  a uh software technique for sharing video between
5:28:54
two programs on the same computer. Not going to  talk too too much about it uh right now but all
5:29:00
of that is true and when we talk about camera cues  we'll get back here but that's the short version
5:29:05
for video inputs. Output devices is the end of the  signal path for video as far as QLab is concerned.
Video Output Devices
5:29:16
The signal path is this: Cues play on stages.  Stages are cut up into regions. Each region
5:29:31
must go to a route. A route connects to a  device. Cues to stages. Stages made of regions.
5:29:43
regions to routes, routes to devices. That is  the whole signal path for video. If you do not
5:29:51
need something complicated, most of the middle  part of that is going to be something you don't interact with, but we're going to talk about  all of it for those times when you do need it.
5:30:03
We are starting at the end, devices. This computer  monitor is a device. Those projectors are devices.
5:30:14
an NDI send from this computer out to the  network is a virtual device. Yeah. So in
5:30:22
the output devices tab we see a list of video  output devices. The first three whose names I
5:30:30
cannot change are actual physical devices.  Device one Decimator in all capitals not
5:30:38
because it's the 80s but because they are very  serious. Decimator is the name of this video
5:30:45
um um scale scaler, right? This is a converter  that accepts HDMI coming in and then does stuff
5:30:54
with it. The main kind of stuff you might  want to do with it is take a signal that is
5:31:00
um of one resolution and feed it into a device  that only accepts video of a different resolution.
5:31:07
But in this particular case, the purpose of  the Decimator is to take a video signal out
5:31:13
of the Mac, come to the Decimator, go out of the  Decimator into this screen, and also come out of
5:31:20
the Decimator and go somewhere else. Uh, no, not  this screen. That screen and that projector. Yeah,
5:31:25
this screen and that projector. Yeah. So, the  Decimator is a hardware split that lets me
5:31:31
and you see the same image, right? We could do  some other clever trickery, but the Decimator
5:31:37
makes it easiest. So that's Decimator. As  far as the Mac is concerned, Decimator is
5:31:47
the name of the display that's attached to  the Mac. So when I go to system settings,
5:31:58
displays, Decimator is the name of  the display attached to this Mac.
5:32:06
If I'm not running QLab, Decimator and this screen  still work this way. Everything's just like this.
5:32:13
Has nothing to do with QLab specifically.  Okay, that's the first device. I'm showed
5:32:20
its resolution here, which is what the device  is reporting, and I'm showed its frame rate, which is what the device is reporting. The second  device is called output one. That is not editable.
5:32:33
The fact that it is not editable tells me  that it is a real actual device. Output one,
5:32:39
which also has a resolution of 1920 x 1080,  I happen to know because I talked with Alec
5:32:44
who configured this system. Output one is  a Blackmagic UltraStudio monitor, which
5:32:50
is a little Thunderbolt connected device that  produces video. QLab has software built into it,
5:32:57
which can communicate with the Blackmagic  device. It circumvents the Mac itself. As
5:33:02
far as the Mac is concerned, there is no  screen called output one. But QLab knows
5:33:07
better. The reason that that's workable is  because Thunderbolt is fast. And so we're
5:33:15
sending data over this fast Thunderbolt bus to  the Blackmagic device. And the Blackmagic device
5:33:21
knows how to take that data and turn it into an  image and send it out over HDMI or SDI. Yeah.
5:33:30
If I had um Final Cut connected, Final Cut would  also be able to talk directly to it because Final
5:33:36
Cut has a driver built in to talk to it. The  fact that it doesn't communicate directly with the macOS, that it doesn't appear in system  preferences, is an advantage to us because I
5:33:45
cannot accidentally shove my mouse off the  edge of this screen and onto that screen.
5:33:50
I cannot accidentally have the menu bar appear on  that screen. If I get a notification that I got a
5:33:57
text message, which should not be enabled on the  show Mac, but if I did, it would not appear on the
5:34:02
Blackmagic device. So, we have many advantages.  What are the disadvantages? One, more money. If
5:34:10
I've got a Mac like this one, which supports  multiple screens, I can just plug the screens right in and they work. Don't have to buy an extra  thing. So that's one advantage. One disadvantage
5:34:21
costs extra money. Second disadvantage, uh, it  takes a little more processing power because I'm
5:34:29
bypassing the macOS's own considerable display  management power, right? But in the modern day,
5:34:39
a new Mac you buy today will have either  Thunderbolt 4 or Thunderbolt 5, both of which have an enormous amount of bandwidth. And  the modern Apple silicon processors dedicate an
5:34:49
uh this is dull so I'm just going to say computer  computer computer stuff it's very fast does good
5:34:56
work thunderbolts no problem so the thing that  makes it technically not as power efficient as the
5:35:05
built-in video is sort of an academic limitation  because in truth it gets it done so who cares
5:35:13
and there's very very little overhead The final  uh version is sort of the final disadvantage is
5:35:19
really just a version of the first disadvantage.  These have a limit uh resolution limit of uh 1920
5:35:25
x 1080 and the 4K models are noticeably more  expensive and physically larger. So do you
5:35:36
have a Yeah, that's is this is what we're using  or this is either this is the monitor. Yeah,
5:35:43
this is the UltraStudio Mini monitor, right?  Thunderbolt comes in here. Video comes out there on either SDI or HDMI. It can only use broadcast  compatible resolutions. If you've got a 1920 x
5:35:56
1200 projector, no, you don't. It's a 1920 x 1080  projector because 1920 x 1200 is not a broadcast
5:36:03
resolution. So, it only supports broadcast  resolutions. It takes up a Thunderbolt port, but it's nice and tiny. You want a 4K one? No  problem. It's about that big. You want an 8K
5:36:14
one. Sorry, that one's this big. Now, it's not  because there's more pixels, right? More pixels,
5:36:19
bigger box. It's not. It's because only their  higher end boxes do higher resolution, and the higher end boxes also do more stuff and have knobs  and buttons and things. They're all compared to
5:36:30
what they offer you, I think they're all extremely  extremely aggressively priced in a good way. This
5:36:36
thing is $130. $130, right? that is phenomenal. 4K  is not quite as amazingly priced. 8K is not quite
5:36:46
as amazingly priced. Whereas the built-in HDMI  port on this Mac Mini supports an 8K monitor. Like
5:36:55
it's you've already got it. You already paid for  it. It's free. So those are the disadvantages. I consider them to be relatively minor, but I wanted  to disclose them. Right? So that's my output one
5:37:07
device. It's 1920 x 1080. It runs at 60 frames per  second and it is in 1080 by 60p mode which means,
5:37:14
1080p60 mode, which means it is 10... it is running  at 60 frames per second, progressive scanning not
5:37:20
interlaced scanning. If you don't know what that  means it looks nicer. That's all you really need
5:37:25
to know right now. My third device is called  output 3 and I happen to know that it is another
5:37:30
one of these guys also built into this case. So,  those are the three physical outputs connected to
5:37:37
my Mac. There's nothing I can do about them  in here because they're real. But devices 4
5:37:44
through 12 are virtual devices. QLab can generate  an NDI device or a Syphon device and send video
5:37:56
out of QLab as an NDI signal or a Syphon signal.  Syphon is simpler, so we'll talk about it first.
5:38:06
QLab makes some video, puts it in memory. I made  that video. Syphon says, draw a box around that
5:38:14
memory and make it available to other software  also on the Mac. So that other software can be
5:38:20
like, hey, look at that. Look at that video  you rendered. I'm going to do stuff with it, too. It's a way of sharing video between  programs that's very, very efficient. The
5:38:30
good news is it's efficient. It's uh cheap for  the computer to do. The bad news is it only works
5:38:36
on the same Mac. So unless I'm running another  video processing app right on the same computer, it's kind of no point to it. But something that  I like using Syphon for sometimes is creating
5:38:46
video in QLab, sending it out via Syphon and then  using that same Syphon source as an input to QLab,
5:38:55
making a camera cue, and capturing that  video back into QLab. Why would I do that?
5:39:00
We'll see when we talk about camera cues.  That's Syphon. If you have a Syphon device here,
5:39:07
you can edit its properties here by giving it  a name, pixel dimensions, and a frame rate.
5:39:17
NDI is another type of output. NDI uses the  network to transmit video. It was created by a
5:39:24
company called NewTek. We have a license with  NewTek to include their NDI smarts directly in
5:39:33
QLab and that allows QLab to produce an NDI send.  NDI signals are much more complicated.
5:39:41
They have pixel dimensions and they have a frame  rate. They also have a pixel format. BGRA which
5:39:48
stands for blue, green, red, alpha, uh alpha is  transparency, is one format where the video has
5:39:55
four channels of data which for each pixel we  have a number that represents how much blue is in that pixel, how much green is in that pixel,  how much red is in that pixel and how transparent
5:40:05
is that pixel. That's one pixel format. Computers  like BGRA. The other pixel format is Y'CbCr 4:2:2,
5:40:13
which let me tell you  rolls right off the tongue. Y'CbCr 4:2:2
5:40:24
is um none of these letters mean exactly  what they sound like they mean. Y'CbCr is a
5:40:29
video transmission standard which separates  luminance i.e. the brightness of any one pixel
5:40:37
with chrominance i.e. the hue of that one pixel.  The reason Y'CbCr exists is because when we
5:40:43
invented color TV and everyone had already bought  a black and white TV, the folks who made TVs
5:40:50
wanted people to buy color TVs, but the folks who  made television said, "If we stop transmitting in
5:40:57
black and white and start transmitting in color,  everyone with a black and white TV will not tune
5:41:03
in. Not everyone's going to run out and buy a  color TV today." And we're not going to spend
5:41:09
double the money to transmit simultaneously in  black and white and color. So what is it exactly that you want us to do RCA Victrola? And what  they came up with was exceedingly clever, which
5:41:20
is the black and white TV signal was considered  to be non-negotiable. The radio wave that goes
5:41:28
through the air and sends a black and white image  from the TV studio to your television is just a
5:41:34
wave that describes a a encoded radio wave that  describes the brightness of every pixel on your
5:41:41
TV according to a pattern so that it updates every  pixel at the right time all across your television
5:41:47
screen. You with me? So when they invented color  TV, they were like, "Check it out. That signal is
5:41:55
going to stay exactly as it is. It's going to  keep telling you about the brightness of every pixel on your TV. And if you have a black  and white television, you're you stay good.
5:42:06
But your color TV is going to be clever enough  to pick up a second signal that's going along
5:42:13
with the first signal. And that second signal is  going to say, "What color is every pixel?" along
5:42:19
with its brightness, which you already know about  from the other signal. And that's chrominance.
5:42:25
Y'CbCr. The Y is luminance. The Cb is chrominance  blue and the CR is chrominance red. And the
5:42:39
remainder of the signal after you figure out  how much red and how much blue to put must be green because all the pictures on your TV are  made up of a mixture of red, green, and blue.
5:42:51
The reason it's red, green, and blue is because  the cones in our eyes are most closely aligned
5:42:57
to pick up red, blue, and green light, although  not truly really. It's much more complicated than
5:43:03
that. And the trap that a person can fall  into, certainly the trap that I fell into, is thinking that there's some fundamental truth  of the universe that means that light is made
5:43:11
up of red, green, and blue components, which  is absolutely not so. But human perception is
5:43:17
closely aligned to what we think of as red,  closely aligned to what we think of as blue, and closely aligned to what we think of as green  in our three photo receptors for nearly all people
5:43:27
that pick up color. So we have these channels,  red, green, and blue. Yeah. Y'CbCr format is
5:43:36
available as a format to send video over NDI.  All of that teaching I just did boils down to the
5:43:45
following. Use one of them. If the picture doesn't  show up on the other end, use the other one.
5:43:51
The truth is that some devices can use either  format and some devices can only use one or the other. If you are sending a video signal over  NDI which requires transparency, you must use BGRA.
5:44:04
If you are using a video signal over NDI that  will be received by a broadcast-savvy piece of
5:44:10
hardware that really is not meant to interact with  computers at all, you almost certainly want Y'CbCr;
5:44:18
is good. The 4:2:2 I  never remember exactly how it breaks
5:44:24
down and it has to do with how nice does  the picture look at the end. And the more twos you see and the fewer fours you see the  less nice it looks. If you see three fours,
5:44:34
it looks really nice. If you see one two,  looks very nice. And if you see two twos,
5:44:39
it looks okay. And if you see only twos,  I think you're not doing video anymore.
5:44:48
NDI can also transmit audio embedded in  the video signal because that's something
5:44:53
that broadcast usually does. HDMI can do  it, SDI can do it, so NDI can do it. You
5:44:59
pick a number of audio channels, 0 to 16,  a sample rate and a buffer size. These are the
5:45:06
defaults. If you want more channels, make more  channels. If you want a different sample rate, go ahead. I don't know why 22,050 is allowed.  I assume it's because it's just a scratch
5:45:16
track that no one cares about. You're trying to  save bandwidth. I don't really know why 96k is allowed. I assume you're plugging into a DiGiCo  which requires 96k. Uh buffer size has to do with
5:45:28
um your tolerance for um delay versus the  possibility of dropouts. The bigger the buffer is,
5:45:37
the higher inherent delay you have in your  audio signal, but the more protected you are against momentary dropouts. The lower your buffer  size, the less delay, but the more likely you are
5:45:48
to have momentary dropouts if your network slows  temporarily. I recommend leaving it at 48 kHz and
5:45:54
512 and just sort of not touching it unless you  discover you need to. Yeah. Okay, great. That's
5:46:02
NDI. These are all now the devices for getting out  of your getting video out of QLab. A screen that
5:46:10
the Mac knows about. A Blackmagic device that the  Mac doesn't know about. NDI and Syphon. Yes. Okay.
Video Output Routes
5:46:21
Now we step up the signal path one step to  the output route. This is the headbendiest
5:46:29
part. This is the part that won't matter to some  of you. It is okay if it doesn't matter to you.
5:46:36
There are people who never need this part. But  there are some people who always need this part.
5:46:45
The route is what connects  the stage to the device.
5:46:52
The name of this route is stream. I created  this route. I gave it a resolution of 1920
5:46:58
x 1080 and I told it that the device  it's playing to is the device named NDI HD. That NDI stream is here in output  devices. Oh, sorry little miss S-i-r-i.
5:47:14
Something I say with the letter S and the  vowel E somewhere in my voice makes her listen.
5:47:30
I don't know what to say. Um and I know  I'm not supposed to call it her. I know I'm supposed to call it it, but I can't help  myself. It has anthropomorphized
5:47:40
itself successfully. Okay, so the route name  stream has a resolution of 1920 x 1080. It's
5:47:47
going to the NDIHD device and it's using the  full raster of the device. Does everyone know
5:47:53
what I mean when I say raster? Okay, great.  Raster is an old-fashioned video term which is
5:48:01
um doesn't really matter as much to use anymore,  but is still useful to use. The raster is the
5:48:08
addressable space of video of a thing. We're going  to go back to the original. The first use of the
5:48:16
word raster is the uh a tube television. The  way TVs worked was there's a little magnet that
5:48:23
you could cleverly control to bend a beam  of electrons getting shot at it by a ray.
5:48:31
And you'd bend the beam of electrons to cross  the backside of the glass of the TV screen and
5:48:38
then go down a little bit and then cross again  and go down a little bit and cross again and keep going. On the back side of the glass, they  painted a bunch of tiny little dots with the
5:48:46
phosphorescent paint. When an electron hits one  of those dots, the dot lights up for a brief time.
5:48:54
When you scan across the dots with the electron  gun very quickly in a very specific pattern of on
5:48:59
and off, you get a picture. Each little dot is  one element of that picture. That is where the
5:49:06
word pixel comes from. Pixel is short for picture  element. Each dot is a pixel on the back side of
5:49:15
the glass of your TV tube. The entire space where  dots got painted is the raster. It's the canvas.
5:49:25
Modern screens don't use an electron gun and  phosphorescent dots. They use little rectangles
5:49:32
made of silicon that glow when electricity is  applied to them. And the amount of electricity
5:49:40
that's applied to them makes them glow a lot or  not as much. And if you put three of them very
5:49:45
close together, one of which glows red, one of  which glows green, and one of which glows blue,
5:49:51
those three together are considered one pixel.  Sometimes it's two green ones together to make a
5:49:56
nice tidy square. That's a pixel. And each color  is a sub pixel, but together it's one pixel.
5:50:05
the number of pixels in this piece of plastic  here all together might be it doesn't matter
5:50:11
what number it is but the whole space where  those pixels are that's the raster so we can
5:50:17
then say okay well in NDI which is imaginary and  ephemeral and virtual the raster is an imaginary
5:50:24
rectangle some number of pixels wide by some  number of pixels high that's the raster of the NDI feed and when that NDI feed ends up in a  device that decodes it and turns it into video,
5:50:35
which is to say a signal that can make  pixels do something. The raster of the video signal gets applied to the raster  of the video display device. Yeah. So,
5:50:47
we've now latched on to this noun. Routes can do  a clever little trick where you can say route,
5:50:57
pixels will come into you and pixels will go out  of you. When they come in, they are some size.
5:51:05
They are a raster of some size. Please apply that  raster to either the full raster of your device or
5:51:15
a small portion of the raster of your device. For  example, you can say, I have a device that accepts
5:51:30
one video signal coming in and supplies  four video signals coming out. Stream,
5:51:39
I am so sorry. I just bumped my lavaliere with  this object and I bet that sounded awful,
5:51:44
especially if you're wearing headphones. And I  really am sorry. I'm going to do it out here. Now,
5:51:50
one video signal comes in, four video signals  come out, and inside this screen, this this this
5:51:57
box is some cleverness, which takes the raster  of the input and cuts it in quarters. And then
5:52:06
each of the outputs is one of those quarters.  Call it a display divider or a display slicer.
5:52:17
When you take an input that is for example a 4K
5:52:23
uh a 4K television signal which is 3840 pixels  by 24. No, this one's interesting. Okay.
5:52:35
One sec. If you send a 4K signal into a display  divider like that and then you cut it in quarters,
5:52:46
each quarter is a full HD raster 1920 x 1080  because the the size of a 4K raster was defined
5:52:55
as four HD rasters together. So, if you have a  display divider like this plugged into your Mac,
5:53:02
which you might because it's a common thing  for folks to want to do, you can tell the route
5:53:10
only send to one quarter of the output devices  raster. This is how you can use four routes in
5:53:18
QLab to turn one big 4K signal into four HD signals  or to take four HD signals, put them together on
5:53:30
a stage that is one big 4K stage, play that to a  route which can then cut them in quarters and then
5:53:37
send that to four output devices or one output  device that cuts it in quarters. Do you basically
5:53:42
understand the idea? even if you don't understand  the practicalities of each. The practicalities
5:53:48
are particular to the device itself. So, we can  talk through those practicalities if you like, if this feels like something you might want to  do, but I want to sort of get the premise in
5:53:56
your heads. This all roots down roots back with  the M1 family of Macs supported only a single
5:54:06
external display, but they had enough processing  power for that single external display to be very
5:54:12
high resolution. And people reasonably thought,  I don't want a 4K screen on my stage. I want
5:54:19
four HD screens. So, why don't I take that 4K  output from from the Mac, cut it in quarters,
5:54:26
and then use those four quarters anywhere I like  on in my theater. And for that, QLab needs to know
5:54:33
that you're gonna cut it up into quarters  so that it gives you four separate signals, but it puts them in the right corner, the correct  corner for the divider to divide it up and then
5:54:44
give you four signals. Yeah. Is this a software  version of what's happening at Buffalo Wild Wings
5:54:53
when you see four TVs just stuck together  with one football game on them? Is that is
5:55:00
that what I'm understanding is like like it's like  splitting and then you can send it four different places. I'm glad you brought that up because I can  actually use that to explain this one way better.
5:55:15
When you go to Buffalo Wild Wings with you, with...
5:55:23
Can you imagine this whole crew just showed  up and they're like, "Hang on a second. Are you here for... Would you like the menu?" No, we  want to look at your TV for a minute. When you
5:55:33
go to Buffalo Wild Wings and you look up over  the bar, there's what looks like one enormous TV showing the football game. But when you look  closer, what you actually see is it's actually
5:55:42
four reasonably sized TVs clumped together really  tightly, all showing each showing one quarter of
5:55:49
a football game. Interestingly, they have chosen  to divide the football game spatially rather than
5:55:56
showing the four quarters of a football game  in time. That'd be interesting, too. Yeah.
5:56:06
My upper left TV shows the  first quarter of the game.
5:56:14
Yeah. Which is why you'll never see such a thing  in Europe because um you don't have you have two
5:56:20
halves, right? Or in Canada you don't you do um  hockey in thirds, right? Um, but they're metric
5:56:26
thirds, which is anyway. Okay, it's not a one big,  it's not one big TV showing one uh showing the TV,
5:56:35
the game. It's four smaller TVs each showing  one quarter of the raster of the game,
5:56:41
right? Why? Because an enormous 4K TV is  extremely expensive. But four smaller HD TVs,
5:56:48
very reasonable. In fact, four smaller HD TVs  are considerably cheaper than one big 4K TV. So,
5:56:56
we have our satellite TV box or our cable box or  whatever or internet streaming thing or whatever, and it's giving me a 4K video signal. I want  to show it up over the bar. If I had to put
5:57:07
a big ass 4K TV over the bar, it'd be a fortune.  So, I take that one 4K signal and I pipe it into
5:57:15
this box and it takes the upper left corner of  that 4K signal and sends it to that TV. Okay?
5:57:22
The upper right corner and sends it to that  TV. Takes the lower left, sends it to that TV, and take the lower right and sends it to that TV  to that TV. If my Mac is plugged into the divider
5:57:34
and it just sends one 4K signal and then those  four outputs make the four TVs, that's easy.
5:57:41
But what if an enterprising person at Buffalo  Wild Wings says, "Oh, no, no, no. I'm going to
5:57:48
take those four TVs. I'm going to separate them.  We're going to see the football game on that one. We're going to see a baseball game on that one.  We see a soccer game on that one. We're going to
5:57:56
see a hockey game on that one. We're going to  spread them out across. So, I'm going to take one 4K raster coming out of my cable box, but that  one 4K raster is going to have four TV shows on it
5:58:08
in the four corners. The divider knows that we're  cutting it in quarters. The TVs don't. How then do
5:58:18
I tell the cable box, give me four shows in the  four corners? That you can't do. But for QLab,
5:58:29
all I need to do is make four video  cues that are not full screen. Four
5:58:37
video cues that are I'm going to have to  um Oh, is this bear? What size is this
5:58:46
bear? Not the right size. Wrong size bear.  Are you 1920 x 1080? You are. Okay, great.
5:58:55
So all I have to do is take four video cues each  of which are placed in one quarter of the raster
5:59:12
1 2 3 4 and then tell QLab that upper left corner  is going to go to the first output on this slicer.
5:59:25
The upper right is going to go to the second  and then my in four individual cues can play to four individual outputs. All the while the  Mac thinks it's doing one 4K screen. Has the
5:59:37
penny dropped? This thing AJA makes one called  the HA4. And there's a new model that's got a
5:59:46
slightly different name, but I like HA4 because  I'm like, "ha, four" just makes me laugh. The HA4
5:59:54
just takes one 4K in, four HD out. This one is  made by Alec. Uh, it's called the Slice 4. And
6:00:01
this is interesting because it takes either HDMI  or display port in and gives you four HDBaseT
6:00:07
outputs. If you have a device that can accept  HDBaseT video, you already know that it's groovy.
6:00:12
If you have a device that cannot take HDBaseT, then  understand that it's just basically like a video
6:00:18
signal over what looks like Ethernet cable, but  it's not Ethernet, it's just video signal. Um,
6:00:24
it's very useful. Uh, Matrox makes one called a  QuadHead2Go, and that one's pretty good. And
6:00:31
then, um, Datapath makes what's widely considered  to be like the gold standard, the FX4 or HX4. Um,
6:00:39
Datapath is great. They're very well built. Um,  the fans are loud and they are very expensive
6:00:45
and the configuration software for them only  runs on Windows, which for me makes it sort of inherently like impossible to think of it as  having taste. But but what... backwards. QuadHead
6:01:00
only runs on Windows. That's right. I'm sorry.  That's right. That's right. That's right. Um, QuadHead inherently difficult to think of as  having taste because it only runs on Windows.
6:01:08
But actually what's really going on is that  Matrox is like heavily invested in selling these things to air traffic control centers  and air traffic control centers are built on
6:01:19
Windows and that's fine. That's, whatever keeps  the planes in the air. I do not care. Um so they have a sort of specific customer pipeline. It  means that when we theater nerds buy a quad,
6:01:28
they're like, "Who are you and why do you only  want one and not 40 of them?" And we're like, "Please don't ask me questions. Sell me the  box and let me go make a play." Um so Matrox
6:01:39
is basically aimed not really at theater um Datapath's  major customer is um um Buffalo Wild Wings or
6:01:48
um the folks who do video displays in the walkway  in the airport between security and your gate and
6:01:55
you're walking past all these big screens that  are like a little fancier than you would expect.
6:02:02
Um that's data path main customer. Um,  and that's why I think it's especially groovy that Alec has brought these things  out because finally a manufacturer of the
6:02:14
display slicers whose customer base is  specifically theater. Um, okay. I told
6:02:22
you this was the most complicated part. That's  output routing. And we're going to go up a step.
6:02:34
Video stages are the thing that cues know about.  A cue plays to a stage and what happens past a
6:02:42
stage is not the cue's business. Everything  we've been talking about for the last hour, not the cue's business. I'm going to hit the edit  button next to this one stage and we're going to
6:02:54
look at the video stage editor. This is the window  that lets me configure a video stage. The stage
6:03:01
gets a name. I named it QClass. It gets its own  layer which is separate from cue layers. We're going
6:03:07
to talk about those in a little bit. It has a  checkbox. Keep rendering between cues. We're going
6:03:12
to talk about that in a little bit. It has a size.  The raster of the video stage is 1920 x 1080.
6:03:22
When you are making a stage, you can think of  the pixel dimensions of the stage as sort of
6:03:31
the home resolution of your project. People  often used to ask, can QLab do 4K video? And
6:03:40
uh my cheeky answer is QLab doesn't know what  4K means. Um 4K is not a meaningful term to
6:03:48
me to QLab. QLab just plays videos and they are  some number of pixels wide by some number of
6:03:53
pixels high. The only important number when it  comes to pixels in QLab is the limit on pixel
6:04:00
dimensions in metal which is the programming  toolbox that we use to build the QLab video
6:04:06
system. And that is 16,3 something4 384. Thank  you. 16,384 by 16,384. The largest any image
6:04:18
can be in metal is 16384 x 16384 and therefore  that is the upper limit of a stage in QLab. Any
6:04:25
individual video can play whatever size it is on  a stage. You saw me play videos bigger or smaller
6:04:34
than the stage. QLab does not care. Just as it  doesn't care what sample rate your audio is,
6:04:39
it does not care what pixel dimensions your  video is. You do not need to convert all your videos to the appropriate pixel dimensions or  frame rate. You just take some video, put it in
6:04:50
your workspace, and play it. This stage is 1920 x  1080 because when I teach this class, most of the
6:04:58
time I plug the system into a projector that is  1920 x 1080. So, that was easiest for me. If we
6:05:08
fast forward some years and the next version of  this class gets built and I find, you know what, the majority of video projectors that I meet  are 4K, then I will make the stage 4K. Um,
6:05:20
but here's the thing, it doesn't matter either  way because the route which receives video from
6:05:28
the stage has another set of powers which I  was waiting until this moment to describe.
6:05:35
You can edit a route and the route has scaling  mode. Just like cues which play to full stage can
6:05:43
either be fit, fill or stretch, routes can either  be center, fit, fill or stretch on their device.
6:05:54
So if I have a stage which is 1920 x 1080 but a  projector which is 4K I can tell the route listen
6:06:10
you're set to fill. So if I have I'm going to  send you a 1920 x 1080 raster from the stage.
6:06:17
But if your device is expecting a 4K raster,  just go ahead and scale up and fill that whole
6:06:25
raster and QLab will do it automatically for  you. Previously to routes being invented,
6:06:31
this was a big hassle. Or you needed one of these  guys. You needed a Decimator plugged in where the
6:06:38
Decimator told the Mac, I am HD, not 4K. Don't  worry, everything's fine. Give me your pixels. And then my output will be 4K and I'll handle  this. But now, clickity clickity and it's done.
6:06:50
Even more of a hassle was I've done my show at  1920 x 1080 and I get to a little rinky-dink
6:06:56
venue with a very old projector that they bought  at Staples in 1997 and it is 1024 x 768. Optoma,
6:07:06
right? Okay, Optoma, listen up. We're just going  to fill that raster. Fill will scale my HD signal
6:07:19
down to 19... to 1024 x 768 because 1024 x 768  isn't exactly the same aspect ratio. They'll
6:07:27
be black either on the top and bottom or on the  sides. But no one cares. The picture will not be distorted. It will be fuzzy because it will be  squinched, but it will be accurate. This alone
6:07:41
in my opinion makes it worth spending 30 minutes  on talking about all this because when I take my
6:07:47
show on my computer and I go to your venue with  your projector that is some number of pixels by
6:07:53
some number of pixels I don't know and I don't  care or god forbid it's through some Crestron nonsense that does who knows what to it. It just  doesn't matter to me because the route takes care
6:08:04
of it and my cues don't even know. As far as  I'm concerned, I'm still doing 1920 x 1080; disco.
6:08:14
If the projector is mounted upside down, I can  rotate the image 180 degrees. If the projector
6:08:20
is mounted on its side, I can rotate the image  by 90 or 270 degrees. If the projector is rear
6:08:26
projecting and either doesn't have the ability to  mirror its output or the infrared signal from the
6:08:33
remote to tell it to do that is being blocked  by the cyclorama which is what usually happens
6:08:39
to me. I can just set QLab to rear project here.  Bada bing. This is the best part. But it takes
6:08:47
so long to explain all the things you need to  know before you get to this part to see why
6:08:54
that's good. And I know that because I've tried  just explaining this part and people are like, "Oh yeah, that seems nice." But they weren't like,  "What is it?" Right? So now you know what is it?
The Video Stage Editor
6:09:08
So here's my stage. It's 1920 x 1080  Masks. What are masks?
6:09:17
If I have Oh, come on. Now,
6:09:26
if I have video playing onto this nice cyc  like I do here, it's nice to see every corner
6:09:32
of every edge, right? But what if my set  designer had built some unusually shaped
6:09:41
piece of scenery and I was trying to fit my  projection into it? For that we use a mask.
6:09:51
A mask is just a black and white  image. Technically a grayscale image,
6:09:57
but critically not an image with any  transparency. Fully opaque pixels only.
6:10:07
When the mask is applied to a stage, it masks out  all the pixels of the stage that correspond to the
6:10:15
black pixels in the mask image. Now, it doesn't  really mask them in so far as masking tape masks
6:10:24
something. What it really does is cut them out.  And that pertains to this layer business I was
6:10:32
about to talk about earlier. And I said we'll get  to it in a second. Because not only do cues have
6:10:37
layers, stages have layers. If I have two stages,  both using the same projector as their device,
6:10:48
and cues are playing to both of those stages,  how should they composite? The answer is the
6:10:56
layer of the stage dictates which cue is in front of  which. All of the cues on the higher layered stage
6:11:06
appear on top of all of the cues on the lower  layered stage. So if I have a stage that is on
6:11:13
layer one and I have a cue on that stage that  is on layer top, then I have a cue that is on
6:11:20
the other stage which is on layer two and it's got  a cue on layer bottom. I still see that bottom
6:11:27
layered cue first because it's whole stage is on  a higher layer. Yeah. So you can think of all
6:11:34
the cue's layers as being nested inside the stage  layers. When you mask a cue I'm sorry when you
6:11:41
mask a stage it cuts away the stage in the black  pixels. So if there is a lower layered stage also
6:11:49
running on this projector you will see that lower  layered stage playing through this dark area.
6:11:56
Yeah, a lot of folks do not need this at  all. A lot of folks do not need this at
6:12:02
all. You could be one of them, in which case  it is fine to blow past this. If I've got an
6:12:07
unusual piece of scenery, though, the mask is a  great way to keep my video off of it. The lower
6:12:12
layer stage would not be off of the  mask. And maybe that's part of the plan. Maybe I've got a frame and I want one  stage which plays video to the inside
6:12:22
of the frame and a second stage which plays  video to the frame. Fun. That's the mask.
6:12:36
The rest of the stage editor is um made up of two  tabs. The layout tab and the warping tab. In the
6:12:44
layout tab, we're going to define how the stage  um how the regions of the stage are laid out. A
6:12:54
region is just a subset of the stage. Plain and  simple. The most common way to do a region on a
6:13:03
stage is to make one region that covers the whole  stage. And that's what we've been doing today.
6:13:08
I've got uh I'm showing the grid for this region.  The region covers the whole stage and every pixel
6:13:18
of the stage is visible on the region. I've  also got a second region which covers the
6:13:26
entire stage and it's being sent to a second  route. The route that it's going to is NDIHD.
6:13:34
NDIHD is the NDI feed which is going out of my  computer and into the computer in the booth to
6:13:41
be sent to YouTube. So every pixel of this stage  appears two times in the universe. One time it
6:13:51
appears here made of light from that projector  on this screen and the other time it appears is
6:13:58
there in YouTube land. Right? Because the  two routes both cover the entire stage,
6:14:06
every pixel of the stage appears in each  route. When I play a cue onto that stage,
6:14:17
this blue rectangle is the raster of the  stage. If I play the cue like this,
6:14:26
every pixel of the stage is  filled with pixels from my cue. All those pixels appear here. All those pixels  appear on the stream. If my cue is smaller than
6:14:37
my full raster, the rest of these pixels contains  no information. So QLab sends black. Jess is good.
6:14:49
In the case of the stream, it sends  clear. In the case of the stream, it sends Hang on. I'm not sure that's so
6:15:01
In the case of the stream, it does send  clear because the pixel format of this NDI feed is BGRA. If the pixel format of this  stream of this feed were Y'CbCr, it would
6:15:11
send black because there is no transparency in  Y'CbCr. Every pixel is fully opaque in Y'CbCr.
6:15:20
But right when I don't transmit pixels or when  I don't transmit information to any portion of
6:15:26
the NDI send that goes to YouTube, it sends  clear pixels which allows groovy compositing
6:15:34
over there in the streaming software. [Music] So  I've got these two regions. Each region covers
6:15:42
the entire stage. Now if I wanted, I could have  regions that cover less than the entire stage.
6:15:50
I could have each of these regions cover only  half of the stage. And now half of my stage
6:15:57
would appear covering this whole projector.  The other half of my stage would appear on
6:16:02
the stream. If you click the grid, will I see it  on the stream? I suppose you will. I hope so. I
6:16:08
have to wait for 30 seconds. Yeah. For delay.  Each half of my stage now gets one region and
6:16:15
each region goes to one route and each route goes  to one device and each device actually produces
6:16:21
visible output. The warping tab lets me define how  the region appears within the raster of the route.
6:16:36
The route accepts pixels from the region, right? But do I want to just fill every  pixel of my route with every pixel of
6:16:44
my region? Probably. But what happens if the  projector is at a funny angle? I want to warp
6:16:50
the output of the region within the route to  counteract the funny angle of the projector.
6:17:01
So here in my layout tab, I'm going to go back to  showing everything full to avoid talking about two
6:17:09
things at once. With the grid showing for my  in room route, I have warped the output here
6:17:22
to counter-correct for the angle of the projector.  Originally, when I had everything one to one,
6:17:36
this image appeared slightly askew because, as  you can see, the projector is slightly askew.
6:17:44
It's actually impressively not that askew given  how far off axis it is, but it is askew. Ideally,
6:17:53
the projector would be like this individual in the  red shirt where you're standing right above your
6:17:59
head would be the perfect place for the projector.  Right? We want to have it shooting straight at
6:18:05
the screen at exactly a right angle where the  center of the lens of the projector is exactly
6:18:11
aligned with the center of the space that I'm  projecting on and everything would be wonderful. The trouble is that in most theaters that place  like not a place where you can put a thing,
6:18:22
let alone a large thing. For some theaters that's  the balcony rail, which is why the two people who
6:18:28
have the most expensive seats sitting on the  balcony rail have an enormous projector with a huge fan blasting hot air in their face.  I'm sorry. Best seats in the house. Yeah. Um,
6:18:41
not the box seats, of course. But we can't put  a projector there all the time. So we move it
6:18:47
off to the side and we warp the corners of the  projection so that the angle of the projector
6:18:57
is being offset by the warping here. Now QLab's  warping facility is quite robust. If I want to
6:19:06
do more warping, I can split this region and  warp it unusually. What if I'm projecting into
6:19:17
the corner of a set? What if I'm projecting  into the corner of a crumpled piece of paper?
6:19:29
Right? What you're seeing the black circle  with yellow is the control point that I've
6:19:36
got actively selected. And when I move it  around, it warps the corresponding sub regions.
6:19:48
If I have complex architecture  that I'm projecting into, this is the view where I can  correct for that architecture.
6:20:01
If I have curvy architecture, I can use bezier  warping instead. Bezier starts with B and bendy
6:20:12
starts with B. That's how I remember instead of  perspective warping which is for straight edges.
6:20:22
There's also a kind of warp called linear. Linear  warp uh is not perspective corrected. And um this
6:20:30
is one of the ones where I'm like, start here and  if it doesn't look good, switch to that and if it
6:20:35
looks better, good. That's my description of how  to use linear warping. Yeah, this is a really cute
6:20:42
question necessarily, but I was curious. I find  this really cool. What's that method for like if you are projecting into something like really for  like tuning your your your warp to get it right?
6:20:52
literally just projecting it, adjusting it, and  then Oh, yeah. Me hours and hours. No, so there's
6:20:59
a couple of different things. Um, when I was  in Provence mapping the projectors in the voute,
6:21:04
Alana, my wife, and I were both hired and we spent  a week each, eight hours a day in the Voute and we
6:21:13
had two iPads. The iPad running QLab remote has  a way to remotely adjust the screen. So we were
6:21:22
sitting, standing there with our pencils. She was  like, "I'm going to take projector 2." And I said, "Great. I'll take projector 6." So we were nowhere  near each other tweaking control points drawing
6:21:33
essentially. And I was sitting there because  because I work for QLab, I was sitting there thinking, if this project were six months later  than today, we'd be doing this in QLab 5 and we
6:21:43
would have been done by now. And then I thought  that at the end of the first day and then the second day I started to think that again and I was  like actually no we wouldn't be done by now. We'd
6:21:51
be done by yesterday. Um the this same process  in QLab 4 was pretty good. In QLab 5 it's very good.
6:22:01
Essentially what I ended up doing is drawing  an inverted image of the architecture here.
6:22:09
That's what you end that's basically what  you end up doing because of math. No matter
6:22:16
how complicated this gets, the amount of work it  takes to play video back remains constant. It uses
6:22:25
something called a lookup table, which basically  says, "Okay, do your crazy drawing." And then once you're done with that, there's like a quick  reference like source pixel belongs here. Where
6:22:35
does destination pixel belong here? Over six, up  12. It's like plays battleship really quickly. Um,
6:22:42
so you don't need to worry about performance  implications of doing advanced warping. Warp away.
6:22:48
The only thing I want to warn you about is that  when your mesh splits number goes very high, this
6:22:54
interface gets pretty sluggy. It's just sluggy.  It's not problematic, but I was uh being a little
6:23:02
glib in a me glib uh in a QLab class and I clicked  all the way up to the maximum mesh splits and then
6:23:08
we watched my cursor beach ball as I just tried to  move one point a few inches. I was on an older Mac and I was like, "Okay, all right, Sam, cool your  jets. Not the best demo." But um you don't need to
6:23:20
worry about any of the performance implications  of using a very warped stage. It will just play
6:23:26
just as easily as if it were un-warped. So yeah,  the answer is you're basically just sitting here
6:23:31
doing it. And you want to do it in a way where  you are standing or sitting ideally if it's going
6:23:37
to take a long time square to the surface with a  nice view of the whole surface that the literal
6:23:44
surface that you're projecting on and able to use  either QLab directly uh you know screen share into
6:23:50
QLab or move your computer down there or use QLab  collaboration which we will talk about tomorrow
6:23:56
or use uh QLab remote on an iPad to painstakingly  move your control points exactly where where they
6:24:02
belong. Other questions? Yeah. How you would like  imagine I have a a complex object like just say
Video on a cube
6:24:15
it's a cube. Yeah. And I can see three sides of it  and I want uh one video on this side of the cube and a different video on other side of the cube  and a third video on top. Would you recommend me
6:24:25
going through and using like the I forget the  word the cue word quaternion, quaternion like
6:24:33
would you recommend me going in and making  several cues and tilting them and smooshing them around so that they land where I want or  is it faster more efficient better to make a
6:24:48
not mask map not math or what Um,  this that make make that. Yeah,
6:24:54
do the waring and do that as opposed to like  adjusting the geometry in the cube. Yeah,
6:25:00
I'd make this do that. And the re Well, it  depends on how many cues you're going to make, right? If I'm doing a bunch of different cues. So  if I have a 3D object here, I can take my stage,
6:25:13
I can make three regions on it. Then I  can warp those three regions so that each
6:25:19
region maps to a surface of the actual  cube that my projector is shooting at.
6:25:26
Make a separate stage for each side of  the cube. Oh, hang on a second. Hang on a second. Let's wait till wait till I finish and  then you can tell me if you still think this.
6:25:37
Each of these regions represents one  actual physical surface of the cube. Right?
6:25:51
Each of those regions uh feeds a Syphon output in  thirds. Intermed. I'm sorry, I'm describing this
6:26:05
badly. I'm gonna start again. I've got four stages  here. Cube top, cube left, cube right. Cube top
6:26:20
projects onto the top of my cube. Cube top is  just a stage where the full raster of the stage
6:26:28
is warped to hit the top of the cube. Cube left is  a stage hitting the left side of the cube and cube
6:26:39
right is hitting the right side. When I play video  to each of those stages, I get all I have to do is
6:26:53
play video to the stage. Uh video output cube  top from the cubes perspective. I'm just gonna
6:27:09
Right. I don't have an actual cube from  the from the from the cue's perspective. I'm just playing to a stage. But the end  result, uh, that's right. I I'm gonna turn
6:27:21
this off because that's copywritten music. It's  beautiful. Aaron Copeland, Appalachian Spring.
6:27:27
Highly recommended. If I had an actual cube that  I'm projecting upon, the warp would be correct. I
6:27:35
can play to the top of the cube only by sending  this stage. But if I want to send to that stage
6:27:49
off I did. You did. Yeah. I also have uh Oh, I see  what I did there. Never mind. I'm I'm mid-flight
6:28:00
on a different version of this demo right now,  which is what's going on, which is why I stalled myself. So now, go ahead, Alec. What's your  recommendation? Uh I would make a difference
6:28:14
top left right like this. Yeah. Without having  that way I can leave the geometry as rather than
6:28:21
needing to like put them in sections of my  stage. So here are three video cues playing
6:28:29
to cube top left and right. And you would  make those three stages to hit the three
6:28:34
sides of the cube. Right. Unless my video  designer handed me a like fancy unwrapped
6:28:40
export from Blender of some sort of single  file that contain pages. Yeah, I hear you.
6:28:53
But here's the thing. Here's also another version  of the same where I'm playing to a single stage
6:29:07
and a single am I
6:29:16
That's odd.
6:29:22
Yeah. Who Who indeed did that?
6:29:38
Yeah, there we go. All right.
6:29:45
Yeah, this is just an in room. Okay. Um, here is  one video wrapped around the corner of a cube.
6:29:54
Right. So this is a single video that I'm playing  to a stage. The stage has three regions which
6:30:03
take bites out of the three corners of the stage.  The three corners. Yeah. The three corners of the
6:30:09
stage. And then those three regions are wrapped  around an imaginary cube. Thus we're missing
6:30:15
25%. Right. The last quarter is absent. Alex's  approach, which I think is also a good approach,
6:30:23
is run three separate cues, one for each  face. If you want to run three cues,
6:30:29
one on each face, this is your way. If  you want to run one cue wrapped around,
6:30:35
this is your way. But of course, you need  a piece of media that understands that the upper right corner is missing. So, for that,  I spent a little more time than I'm proud of
6:30:47
figuring out how to render. Where are  you? Rain cube corner. Rain cube corner
6:30:58
was rendered in Apple Motion. 3/4 of a square  that produced one ideally sort of theoretically
6:31:09
continuous image of water sort of spraying out  of the corner of the top and pouring pouring
6:31:16
down both sides. I could do it in Blender  and that would take even more more time,
6:31:21
but I thought I'd just do it, you know, the cheap  way quicker and this even this took a long time.
6:31:27
But this is a piece of imagery which  is analogous to what we were talking about with the display slicer. The source  material understands that we're only using
6:31:36
three quarters of the square. The surface,  I'm sorry, the stage with three regions.
6:31:43
Those three regions all play to one route  but use different chunks of the route. And
6:31:52
that one route plays to that projector here.  The purple rectangle with the gray background
6:31:58
and the grid lines represents the projector,  the device that the routes are playing onto
6:32:08
make sense. Okay. Not like super  straightforward. But what we've
Video output wrap-up
6:32:17
now done is gone all the way up the signal  path and made a stage in this case warped
6:32:25
for the in room version of the of the  region not warped for the stream version
6:32:37
where this same space is where all of our cues  are going to. And that same space doesn't need
6:32:43
any real adjusting when I take this class and  go and do it in some other venue. Even if I'm
6:32:50
streaming or not streaming, who cares? The  one that sends to NDI doesn't go anywhere. If I'm plugged into this projector, great. If  I'm plugged into another projector, great. So,
6:33:00
that's stages all the way up. Do people  feel as though they basically understand
6:33:06
it? It's okay if you don't all the way  understand it. Like with many things,
6:33:12
the first time you hear something is unlikely to  be the time that you're going to really latch. What's going to what's going to happen is  the next time you need to deal with this,
6:33:21
it won't feel like a foreign language. It'll feel  like a thing you remember but don't quite know.
6:33:28
And you'll muddle your way through. And then it'll  then the next time you do it, you'll be like, "No, I remember. I went to class. I learned how to do  this. Then I sat down and did it myself. It wasn't
6:33:36
that easy. Now this time I remember all the things  I did and I remember all the things Sam said and all that put together means I can do it this time.  No big deal. That's usually how this works. Okay.
Video file formats
6:33:57
Video formats. So I said we would  talk about this in the future. Um,
6:34:03
what types of video files do you you want  to use when you're making video for QLab? It matters more than for audio. For audio,  it's easy. Use AIFF, WAV, core audio format,
6:34:14
or MP3 or MP4. And it turns out that that's almost  all audio files are in one of those formats. You
6:34:21
actually have to go out of your way to find an  audio file that's not in one of those formats. So, you're pretty much good for video. The  most common file format for video these
6:34:31
days is actually one of my least favorite. So  that's why we have to have a little lecture here. The short version is these are the  types of files that I want to talk about
6:34:41
today that are the most relevant to QLab and  my attitude towards them is basically that
6:34:51
ProRes 422 proxy. It's the first  format of video I want to talk about.
6:34:56
It is um uh it's a format that was invented  by Apple. Uh they make large file sizes.
6:35:03
Chris wants me to stop. Sorry. Our  NDI when we when we adjusted the region got stretched in a funny way.  I think we need to somehow reset it.
6:35:16
There it is. There it is. Thank you. Yeah,  you bet. I love streaming. Yes, I do.
6:35:23
Um, ProRes 422 proxy uh is... ProRes 422 is a family  of video formats that was invented by Apple
6:35:31
um designed largely around the um they're designed  as what are called intermediate video
6:35:37
codecs. Your camera shoots in one form, you edit  in another and then the the customer receives
6:35:44
the final edit in a third form. This is an  intermediary codec codec. Then it turns out that
6:35:50
the codec is really good and so people started  making cameras that can shoot in 422. All right,
6:35:56
so Blackmagic and a few others make cameras that  shoot directly to ProRes 422 and that's pretty
6:36:01
groovy. But either that's neither here nor there.  ProRes 422 proxy makes pretty large files. If you
6:36:09
have a a video that you've bought from Pixels or  wherever and then you re-encode this 422 proxy,
6:36:15
it's going to get big and you're going to be  surprised by that. Don't worry about it. No big deal. It has really nice picture quality. Um,  there are no ugly gradients, but it does have soft
6:36:26
edges. That is, its Achilles heel is soft edges.  Uh, the truth is that those soft edges are usually
6:36:34
not a problem in a real theatrical context.  Um, I'll talk more about that in a sec. Uh,
6:36:40
you don't need a lot of GPU or CPU power um  to render and play back ProRes 422 proxy and
6:36:47
it's hardware accelerated on Apple Silicon. Um,  but you do need plenty of memory because it's a
6:36:52
large file. The codec itself is free, but the only  way to gain access to it is through Final Cut Pro,
6:36:59
Motion or Compressor, which are Apple's video  tools. There is sort of a roundabout tricky way to
6:37:05
um do it. And some other media encoding software  has built-in support for 422. So you can,
6:37:12
for example, if you use uh Adobe Premiere or  After Effects, they can encode directly to Final uh to ProRes 422 as well. Um Adobe Media  Encoder is one of Adobe's media encoding tools.
6:37:23
Um Adobe Media Encoder has a bug. It has had this  bug for a minimum of 20 years. It once in a while
6:37:31
generates files that are a little glitchy. No  one really understands this that I've met. It is
6:37:38
non-negotiably true and people who have observed  it to me are Adobe lovers and Adobe haters and
6:37:43
Adobe agnostics. So, I know it to be true and  it drives me crazy. The only answer here is just
6:37:50
don't use Adobe Media Encoder to encode video.  Use the built-in encoding tools in After Effects
6:37:56
or Premiere. Or if you do use Media Encoder and  you get glitchy playback, re-export it through
6:38:03
Compressor. Compressor is only 50 bucks and it's  really useful and I really recommend it if you're
6:38:09
routinely working with video. Compressor is the  best tool that I've seen to open any kind of
6:38:15
video and save it as any other kind of video and  including uh some very minor editing tools built
6:38:20
into it. So ProRes 422 LT is one picture quality  step higher than Proxy. Even larger file sizes,
6:38:32
superb picture quality, no gross gradients, no  jaggy edges. The def the deficiencies of this
6:38:39
codec are seldom visible in a theatrical context.  Sometimes people look at 422 proxy and they say,
6:38:45
"Listen, I looked at that video on my $50,000  reference monitor and I found that the edges
6:38:51
are soft and therefore I think it should not be  used." And I say, "And is your $50,000 reference
6:38:57
monitor going to be installed in the set to  display the video to the audience?" Oh no, you're going to use a projector, which is in  the back of the theater, which is projecting
6:39:06
through 60 ft of humidity onto a literally soft  surface. So, the soft edges in your picture are
6:39:16
in fact meaningless compared to the atmospheric  effects and the physical effects. Not to mention
6:39:22
the fact that I'm front lighting myself and  so there's bounce uh onto the psych that's uh
6:39:28
washing out my picture slightly and my lighting  designer hasn't even showed up with the hazer. So
6:39:36
your soft edges you see in your perfect pristine  studio setting are unlikely to be relevant in an
6:39:42
actual live context. It's the same thing you say  to folks who are obsessive about sound quality,
6:39:49
about their recordings, and then go to a theater  and then are playing through like an amplifier that buzzes. Like, I mean, okay, but you're  the whole thing only looks as good as the worst
6:40:01
looking thing. That said, feeding garbage in, you  get garbage out. So, you want to start with a good
6:40:07
picture, but you needn't obsess over it being  a perfect picture. That's my point.
6:40:14
It has the same CPU, GPU, and RAM story as 422  proxy. You don't need that much CPU or GPU. You do
6:40:20
need a good amount of RAM because the file size is  large. PhotoJPG is an interesting codec because
6:40:26
it's very flexible. When you render a PhotoJPG  movie file, there's like a slider that's called
6:40:32
quality, and it's a scale from 0 to 100, which  I assume is percent good-looking. I don't know.
6:40:38
When the slider is all the way all the way  to the top, the picture looked great and
6:40:44
um uh it requires a lot of system resources to  play back. When you set the slider lower, you
6:40:51
use less system resources to play, but the picture  doesn't look quite as good. Uh I think that very
6:40:58
high quality looks superb and very low quality  looks terrible, but it is subjective and it really
6:41:03
matters what kind of imagery you're rendering. If  you have a Mac that you are pushing to the limit,
6:41:10
you can consider using pro using PhotoJPG,  render like little 30 second clips at 100 quality,
6:41:18
90, 80, 70, 60, 50, 40, and play back these clips  and use the clip that has the best picture quality
6:41:28
without overtaxing your computer. So you may  be on one particular setup, it's like, oh yeah,
6:41:34
70 works great and looks fine. Maybe 60. Now,  this part of this lecture is getting rapidly
6:41:41
outdated because the cheapest Mac you can buy  new, which is sitting on the desk in front of me,
6:41:47
would never even need to be thought about this  way until you're like, what are you actually
6:41:52
doing? Oh, yes, I'm playing back 12 8K videos at  the same time. Like, okay, we'll talk. But mostly,
6:41:59
this is kind of an outdated idea and you should  just render it in ProRes proxy and get on with your day. H.264. H.264 and H.265 are interesting  and valuable and technically sophisticated and
6:42:12
um they made a really big advance in the field of  video that was very important. Some say H.264 and
6:42:20
265 looks better than PhotoJPG. I disagree.  I think it only looks better than crummy PhotoJPG H.264 is hardware accelerated on Macs  all the way back to the early 2000s. So there
6:42:32
was a time where H.264 was a great choice  if you had a really pokey Mac. H.264 and H.265
6:42:41
are temporal codecs. And this is the cleverness.  Just like MIDI timecode is 1 2 3 4, 2 2 3 4, so too
6:42:52
is H.264 and H.265. When you encode video that's  30 frames per second. The first frame of every
6:42:59
second is a full picture of all the pixels in the  frame. Then the next frame is just the pixels that
6:43:05
changed. Then the next frame is just the pixels  that changed. And this keeps going until you get to the end of the second. And then at the second,  the first frame is the whole frame. Okay, cool.
6:43:18
That's why YouTube runs so well even on crummy  internet connections because it can just pipe down
6:43:24
a lot of this data really quickly, especially when  so many YouTube videos are a really nice static
6:43:29
shot of a very well-laid out room and a person in  a small percentage of the shot talking and holding more or less still. It's perfect for that because  all those pixels don't change. Just these pixels
6:43:41
change. But try to scrub ahead, try to scrub  back, no good. Play the video faster or slower
6:43:49
than normal, no good. H.264 and H.265 are perfect  codecs for internet delivery. All of their good
6:43:58
powers are designed to make internet delivery,  streaming delivery ideal. But all of their
6:44:04
deficiencies come into play when you use it in a  live playback context. So, while it's technically
6:44:11
compatible, it's not recommended. Yeah. Is that  the reason for like the confetti effect? Do you
6:44:17
know what I'm talking about? I don't know if I do.  When you're watching a video on YouTube and like
6:44:23
watch like Macy's Thanksgiving Day parade and they  have the reporter and then they like quickly cut to like a wide shot and there's tons of confetti.  The quality of the video just plummets. Yes.
6:44:34
Because they have to refresh so much. Yes.  That is the reason so many pixels changes.
6:44:39
Okay. Um more sophisticated versions of uh of  more sophisticated temporal codecs. I think 265
6:44:46
might do this. Dynamically decides how many frames  should be full encoded frames and how many frames
6:44:53
should just be difference frames based on the  picture content. I'm not certain of that. Check
6:44:59
me check my work. H.265 is definitively  better the same way that MP4 is definitively
6:45:05
better than MP3 for audio. It just sounds  better at the end. No discussion. Or discussion,
6:45:11
but you're wrong. Like you are wrong. MP4 and  MP3 encoded at the same bit rate; MP4 sounds
6:45:20
better. Non-negotiably true. Or MP3 and MP4 the  same piece of audio encoded so that the two file
6:45:28
sizes match. MP4 sounds better. It just does. And  the same thing is true with H.264 and H.265
6:45:35
video. One is just better, the end. But I don't  know if that exact thing that I said about the
6:45:40
dynamic key frames happens to be one of the things  that makes it better. I'm not certain of that.
6:45:45
I do know that some video formats and some video  encoders can dynamically set key frame. Oh. Um,
6:45:53
this is a little bit of a nerd sidebar, but  sidebar, but the confetti question and it
6:45:59
helps our our collective deeper understanding  of what's going on with video. You know how I
6:46:04
talked yesterday about the Nyquist theorem and  about how many samples per second to get high
6:46:10
frequencies. So, all of that math is still true  for video because video is two-dimensional signal,
6:46:18
noted one-dimensional signal. So it if you're  curious about this, it's fun to look into the the
6:46:26
same math that compresses audio signals that those  same principles are at work for video signals. So
6:46:33
if you have an image that has what in in an image,  what is high frequency information? Confetti.
6:46:41
Because it's a lot of changes from light to dark  to light to dark in a short space of the image.
6:46:46
That's high frequency image information. It's  frequently changing and it's frequently changing
6:46:51
in the image. So, uh you'll notice this when  you're saving, but like if you take a a photograph
6:46:58
and you're trying to figure out why the file  ch size might change dramatically depending
6:47:03
on what's inside the photograph. It's because how  much high frequency information in the photograph
6:47:10
will determine how much uh file storage it takes  to recapture and recreate what's in the image. If
6:47:18
you've got uh the compression math is doing the  same stuff. So if you've got mostly big fields of
6:47:23
color, there's not high frequency information,  you can compress that out and it still looks
6:47:28
pretty good. If you have lots of edges, lots  of high detail, lots of grass, lots of leaves,
6:47:34
confetti in the air, then that's high frequency  information and you need a lot more data to
6:47:41
recreate it and not be fuzzy and blurry. So,  exact same math now with images instead of sound.
6:47:48
the uh I'll go one step simpler and say let's  encode a text a piece of text. Um and the text is
6:47:58
75 copies of the letter A. So you just encode that  as A x 75. Okay, great little tiny piece of
6:48:07
information. I send it to you. You can decode that  real easy. But if I randomly mash on the keyboard
6:48:14
for 75 characters, it's much more difficult to  find patterns that you can encode down into a
6:48:19
shorthand version. So I have to send a larger  amount of information to you for you to decode.
6:48:27
Um, how I know for sure that there is someone  in charge at HBO who doesn't know anything about
6:48:34
video? Because when HBO went to streaming, did they  change their opening logo slate of the white TV
6:48:43
snow, which is a custom-designed image to foil  streaming quality, right? When you have a good
6:48:52
strong internet connection and you watch  something on HBO, you know, if you're watching,
6:48:58
if you're binge watching something, you watch the  episode, then you see the title slate for the next
6:49:03
episode and then you watch the episode. So, when  I watch, you know, whatever, Game of Thrones, first of all, has to be a very, very dark room because  the dynamic range of Game of Thrones is like six
6:49:15
black to deep gray. That's an aesthetic choice  which reasonable people may differ on whether
6:49:21
it's a terrible choice or just a bad choice. But  when you go through the whole episode with a good
6:49:27
strong internet connection, it's all crisp and  beautiful and everything looks great. And then the moment you hit the next HBO, that slide thing with  all the snow and the HBO logo, it looks like your
6:49:40
stream drops. Everything looks blocky and chunky  and something's wrong and you're like, "Oh no, did my modem need to I restart my router?" No, it's  just that that white snow image is un-compressible
6:49:53
and as a result, it looks terrible even on a good  internet connection. That's how you know for sure
6:49:59
that someone who's in charge at HBO doesn't  understand anything about video. What should they have done instead? They should have recreated  that image, I think, to be a more digital version.
6:50:12
At minimum, they should have taken the block size  of their compression algorithm and made each block
6:50:18
of the snow animation that size. So that the  chunky gritty like gritty effect that you see
6:50:27
would be aligned with the grid of the noise in the  image. I think that would have looked pretty hot.
6:50:35
Or they just I don't know use a little imagination  and come to a new version of HBO that is new and
6:50:43
that doesn't call back to a picture quality.  Like my daughter, who's who you've been hearing,
6:50:48
she's never going in her entire life to turn on  a TV and see white snow because that technology
6:50:56
is gone. Analog transmission over the air and the  possibility of switching on a television that's
6:51:02
tuned to a dead air station that just doesn't  exist anymore. And that snow is a harkening back
6:51:09
to something that doesn't exist and the reference  point is gone. Right? What do you say when
6:51:14
you end a phone call? What am I doing? Hanging up.  How many people have hung up a phone recently?
6:51:21
On what? We don't hang up the phone. We turn off  the phone or I don't know what. But hang up is
6:51:28
this weird like vestigial thing, but the handset  no longer hangs on a hook on the wall like it used
6:51:34
to. When you the save button in Microsoft Word,  it's a little disk icon. Young people look at it
6:51:42
and say, "Excuse me, what is that? Why does it  mean save?" And it's a reasonable question. I
6:51:49
have no idea why it means save. Oh, I guess it's  a floppy disk. What's a floppy disk? And why is it
6:51:54
floppy? Well, there's floppy disks and there's  hard disks. Well, actually, there's neither anymore. There's solid state disk. Well, what's  the difference between hard and solid state?
6:52:02
Hard seems kind of solid. It all is like these  metaphors on top of each other, some of which
6:52:08
have no... the original reference point is gone.  So the HBO snow for me is like, okay, I get it,
6:52:15
but it doesn't... like, it both doesn't make any  sense and looks, like, specifically terrible with
6:52:23
online streaming encoding. So that's just my  opinion, but it's interesting to think about how
6:52:30
those two things interact exactly. ProRes 4444  is one of the only one of two only two moving
6:52:39
image file formats in QLab that has alpha channel  support. If you have a moving image video format
6:52:48
and you need transparency, this is one of the two  that you need. ProRes 4444. It's a mouthful. Huge
6:52:59
file sizes. Truly huge file sizes. It needs the  most system resources of any of the video formats
6:53:06
we've talked about today. It looks terrific. Is  it pouring? Yeah. Okay, great. That was not in
6:53:15
the forecast recently. Um, it is very very hard  to see the deficiencies of 4444. All but the most
6:53:25
trained eye will be unable to tell the difference  between ProRes 4444 and truly uncompressed video.
6:53:33
HAP and HAP Alpha are the last two video formats  that I want to talk about as being supported in
6:53:39
QLab. They're interesting. Um they were invented by  VidVox, which is a software outfit that publishes
6:53:45
the excellent and very complicated piece of video  software VDMX. Um uh you can think of VDMX not so
6:53:55
much as a program as it is a toolbox to build your  own program to do VJ stuff with. Um they were sick
6:54:03
of trash talking H.264 without having something  to suggest as an alternative. So they invented HAP. It looks as good or better than ProRes at  equal file sizes. Um, so if I have a 100 megabyte
6:54:17
ProRes 422 file and a 100 megabyte HAP file, the  HAP looks at least as good, usually better. The
6:54:24
performance on equal hardware is two to 10 times  better than ProRes. So, even though my picture
6:54:32
quality is equal, the same computer that can play  back two ProRes 422 files simultaneously without
6:54:41
dropping frames will be able to play between  four and 20 HAP files of equal resolution without
6:54:49
dropping frames. It's very very impressive. It  needs third-party tools to encode and these
6:54:55
tools are not intensely maintained. So, it can be  a bit of a workflow hassle to use HAP. You cannot
6:55:01
just grab a video file that is encoded in HAP in  the macOS and hit spacebar and preview it. When
6:55:10
you do that, you will just see a thumbnail that's  the first frame of the video. It's a bummer,
6:55:16
but it's not directly supported by the macOS.  You've got to use other tools to do it. That's just true. Um, and that's sort of a pain in  the neck, but it's very very groovy. So, uh,
6:55:28
if you're willing to do the extra administrative  work to deal with it, you can really pay off big.
6:55:34
If you're trying to do a very video-intensive show  on a lackluster computer, you may find that using
6:55:41
HAP or HAP alpha, which has transparency support,  um can get you over the threshold of what you the
6:55:47
amount of playback that you need to be able to  do. That is moving image video formats lecture.
6:55:54
Are there any questions? Though you did a  great job of interspersing your questions, so I applaud you. Still images, it's even easier.  PNG, JPEG, GIF, TIFF, the end. But use PNG or
6:56:09
JPEG. Just don't like don't don't run yourself in  circles doing weird things because GIFs are weird.
6:56:16
Animated GIFs, if you drop them into an image uh  playing program that is expecting a still image
6:56:22
can act funny. Um, some people like to use PDFs  in QLab. PDF is a mysterious file format full of
6:56:29
Eldrich horror. You can have code in a PDF.  You can have scripts in a PDF. A PDF can have
6:56:36
an embedded web server in a PDF file. Just save  yourself the trouble. Make a JPEG, make a PNG,
6:56:43
and get on with it. TIFF, if picture quality is  of the utmost importance, but TIFF file sizes are also very large. But that's still images.  It's really a lot more straightforward. Okay.
6:57:03
You're running. Yeah. Great weather. Great  weather, right? This is my mid-Atlantic
6:57:10
rainstorm, no thunder. Yeah. Camera cue. This  is a camera cue in QLab, which is using as
Camera cues
6:57:21
its source the FaceTime camera on my laptop.  The laptop is running QLab. The output of that
6:57:32
copy of QLab is an NDI feed which is going over  our private Wi-Fi network that this computer has
6:57:41
access to. The camera on the Mac is playing to a  camera. The camera cue is playing full screen to an
6:57:49
NDI feed. The NDI feed is being picked up by this  computer. And that NDI feed, Sam's laptop, Saturn.
6:57:57
Sam's laptop NDI. Saturn is the um macOS name  of this Mac. Sam's laptop NDI is what I named the
6:58:06
NDI feed inside QLab on this Mac. And that appears  as the video input for this camera cue. You can
6:58:14
see the latency is mediocre. The picture quality  is superb. Um, or as superb. Oh, the latency is
6:58:24
worse than mediocre. The faster I move, the less  happy it is, but the picture quality is really,
6:58:31
really good. Um, this is an M4 MacBook, which is...  Apple updates the camera in their laptops
6:58:39
basically um once every geological era. This is  the most recent camera and I think they actually
6:58:46
did meaningfully improve its picture quality.  Not a ton, but a good amount. And so you can see,
6:58:51
you know, individual beard hairs. It's not just  a mushy beard space. Um, and of course you can
6:59:00
see the picture behind me and the letters are  fairly crisp. So the picture is doing a good
6:59:05
job. The camera is doing a good job and NDI is  doing a very good job of encoding the picture quality and sending it over there. The reason the  choppiness is because we are really slamming the
6:59:15
network in this theater with this particular demo.  So I'm going to move on from that. We can also use
6:59:27
the NDI cameras which are already being used for  the stream and therefore not tax the network extra
6:59:35
because this NDI stream is already being supplied  fed into the network. So I'm just taking a second
6:59:43
copy of that out. So the network is not now being  extra taxed. And to show you something about QLab,
6:59:51
I can add another copy of the camera. QLab just  takes the pixels in once and displays them twice.
6:59:58
So these two cameras, however much latency they  have, the two of them remain perfectly in sync
7:00:05
and will always. I can even add another two copies  and all four remain in sync. Right? Piece of cake.
7:00:18
In a camera cue, you have the I/O tab which  has a video input and here we choose one
Camera cues - the I/O tab
7:00:27
of the video input patches which we talked  about earlier. It has audio input optionally
7:00:35
and it has um in the case of NDI the NDI  stream. No, let me explain this better.
7:00:43
If a camera cue is using a patch that uses NDI  video, that camera cue can only accept audio from
7:00:53
that NDI stream. And if that NDI stream has no  audio, then that camera cue cannot accept audio.
7:01:01
If however the patch for a camera cue is using  any other form of video, you're allowed to use
7:01:10
any audio input patch on that same camera  cue at the same time. So let's for example
7:01:21
go into workspace settings to video inputs
7:01:31
and choose this UltraStudio Recorder 3G.
7:01:40
In this case during lunch, Alex swapped out  one of the video the Blackmagic output devices
7:01:46
for a Blackmagic input device called  UltraStudio Recorder 3G. And Chris, this is Chris'. Chris loaned me the use of his  lovely Sony. When this camera is on and running...
7:02:06
it is just different... I have an A7 III; this  is an A74. They are just different enough that it
7:02:12
feels as though I have never heard of it before,  which is really quite something. Well done,
7:02:17
Sony. Um, with this UltraStudio Recorder  3G, I can accept any video input up to HD
7:02:27
signal quality in uh via HDMI or SDI. I  can hit the monitor button and look at
7:02:36
the live input from my device at any time.  Once I'm sure I like it, I can then use
7:02:47
that device for my cue. Since I am using  anything other than NDI as the source,
7:02:56
it is now possible to use an audio input. So, if  I had a microphone next to this camera and the
7:03:02
microphone were plugged into my Dante device,  I could use that Dante device and use main
7:03:09
input patch and have a built-in mic cue built into  this camera cue. I choose not to at this time.
7:03:18
We also on the I/O tab have a video output  and an audio output side, same as others.
7:03:29
The geometry tab looks just the same  as it does for a video cue. And the video effects tab looks just  the same as it does for a video
7:03:37
effect. There is no time and loops tab  because there is no fixed timeline for
7:03:46
uh for a camera cue. So when I run this camera,
Camera cues - the Video FX tab
7:03:56
this is a video uh this is a  video effect-laden video cue,
7:04:05
but I think it might be worth seeing it  with no effects for a moment just to show
7:04:14
how much um fidelity we can  get out of a Blackmagic card.
7:04:23
Pretty good. The camera itself is very good  and everything the camera has to offer get
7:04:33
caught by the Blackmagic card. Right?  This is the way to fly in my opinion. If
7:04:39
you want to bring in real video into QLab  and you really care about how it looks,
7:04:53
there are also some other fun things you can  do. Well, no, we already did that. Hang on. Um, I wanted to point out someone asked me once  about using QLab as like a multicam viewer,
QLab as a multicam viewer
7:05:04
and it occurred to me that  that is actually possible.
7:05:11
Um, let's see. Let's make this.
7:05:24
So, here's a four-way multi-cam display. Four  cameras in this room. The three NDI cameras up
7:05:30
there and this one down here. And I've got them  all four playing in quadrants. Or I could spend
7:05:38
$2,000 on a multicam view piece of hardware  and then slap a monitor on it. And can I point
7:05:45
out again that this is running off the base  entry level Mac Mini. That is not something
7:05:51
we would have ever done this class on four  or five years ago. Uh it's pretty astonishing
7:06:01
how far the the current generation of Apple  Silicon has come for for for everything but
7:06:08
for video in particular. I mean, this is the the  cheapest entry- level Mac Mini is doing this. And
7:06:18
yeah, and to be clear, we're we've added a piece  of input hardware here that's about 130 bucks,
7:06:24
which takes the HDMI in from this camera.  While this camera is a pretty pricey camera,
7:06:29
any camera will do. We also have three  NDI video cameras that are feeding onto
7:06:36
the network. Those are, I think, one fairly  high-end and two quite mid-range uh cameras.
7:06:46
Yeah. All they're all um they're all  AIDA, right? Um all from a sort of
7:06:55
uh sort of middle of the road. You can  get some very expensive cameras which look phenomenal. You can get some  cheap cameras which look cheap. Um,
7:07:02
the cheapest worthwhile camera that I found  is a little security camera for about 200
7:07:07
bucks with a lens. It doesn't look great,  but it looks okay. Marshall makes some good
7:07:12
inexpensive cameras. AIDA makes some good fairly  inexpensive cameras. Um, but I wanted to point
7:07:20
out that you can actually QLab can actually be  used as a fairly reasonable video switcher.
QLab as a vision mixer
7:07:28
So, I've got four camera cues here. Each of them  is set to play on a layer bottom, and each of them
7:07:37
has a hotkey trigger, and they're all set to fade  and stop peers. So, when I hit one on my number
7:07:45
pad, I get one camera, two is the other camera,  three is the third, and four is something I
7:07:58
failed to program properly. There we go.
7:08:04
So, I'm now just using hotkeys to switch  between these cameras pretty effortlessly.
7:08:11
That one is not working great, and that's  because the way Blackmagic turns itself on and off when you stop playback. So,  I'm going to try a trick where I leave
7:08:22
the monitor window for that camera  open and see if that keeps it happy.
7:08:35
Yeah, Blackmagic is clever enough to notice when  it's not being used and it shuts itself off. So,
7:08:42
the monitor window prevents that from oh, no,  not quite. All right. Well, you get the picture, though, I hope. And if I did this with opacity  fading instead of just fade and stop peers,
7:08:52
I wanted to set this demo up as quickly as  possible. But if I could instead programmed it so that it faded each camera cue  down to zero opacity but kept it running,
7:09:01
then the Blackmagic device would not shut  itself off and you wouldn't get this drop out. I am monitoring the video input or  I'm trying to monitor the video input. Oh,
7:09:10
that's the output. Oh. Oh. Oh, I failed to do  this. I failed to do what I thought I was doing.
7:09:17
T-shirt.
7:09:29
Yeah, that is exactly what I thought I was doing  and it worked. Excellent. Now, while I'm doing
7:09:36
this, you say I say to you, "So now, why exactly  are you spending $20,000 on a Tricaster?" And
7:09:43
you say, "Well, it does nice lower thirds  titles." Okay, fine. I can do those, too.
7:09:55
And that's my video switcher demo. I set it up  in 20 minutes. If I set it up in 30 minutes,
7:10:01
it probably would have run a little bit  smoother, but I wanted to make the point.
7:10:08
That's camera cues. Do you have  any questions about camera cues?
7:10:17
No. Okay, great.
7:10:24
Yeah, escape. Um, it's it's stuck. It won't I  mean, it's great. It's great, but it's a bit
7:10:32
much, Sam. Okay. Text cues are the third type of cue  that generates video output from QLab. We have the
Text cues
7:10:40
basics and triggers tab. We have the I/O tab, which  you know all about. We have the geometry tab, which you know all about, the video effects tab,  which you know all about, but instead of a time
7:10:48
and loops tab, we have a text tab where you can  type in text. That text can be styled with any
7:10:55
font you like, pardon me, any font you like, any  color you like, and any background color you like.
7:11:05
Once a video uh once a text cue is playing, it  just is another video cue. So everything works
7:11:15
on a video cue that works on everything works on  a text cue that works on any other kind of video cue
7:11:26
including blend modes. Right?  That's kind of it for text cues.
7:11:33
While a text cue is running, its  output is essentially a PNG image.
Snow White demo
7:11:46
This is a demo that I like to do to demonstrate  um the sorts of things that are possible with
7:11:52
tools built into QLab and nothing outside QLab.  And I'm gonna um I'm gonna open this monitor
7:12:00
because I need to look at what I'm doing and I  don't want to keep twisting my neck around. So,
7:12:07
this little animation uh in homage to the  original multiplane camera, which was the
7:12:14
Walt Disney Company's true magic invention that  made cel animation as we know it possible.
7:12:21
It was a camera that was used to film animation in  which it was filming down onto a series of glass
7:12:28
plates. The glass plates were hooked together on  a rack that could be moved closer to the camera
7:12:34
and farther and which could be spread apart or  brought together to allow the camera to simulate
7:12:39
the kind of depth of field effects that happen in  reality with a real camera filming a real set. So
7:12:47
here we have layers in QLab. On the background we  have layer one. We have the background image that
7:12:56
is a still image of a you know mountainscape with  a slight blur effect on it in QLab. On a higher
7:13:04
layer we have Snow White herself. On a layer  higher than that we have that oak tree. And on a higher still layer we have some shrubbery in the  foreground. You will bring us a shrubbery. If we
7:13:16
want Snow White to walk across the stage, and this  is not a perfect simulation of walking because her skirt doesn't billow, all we need to do is  use fade cues to slide the other elements the
7:13:28
opposite direction. And we slide the foreground  elements faster than the background elements.
7:13:34
To push in on Snow White, all we need to do is use  fade cues to change the scale of the foreground
7:13:42
elements faster than we change the scale of the  background elements. If we want to rack focus to
7:13:49
Dopey, he's back there with a blur on him. So,  all I really need to do is reduce the blur on
7:13:57
Dopey at the same time that I increase the blur  on Snow White, which is just again a fade cue,
7:14:04
adjusting parameters of the video effects on these  images. I also did a little bit of focus breathing
7:14:11
simulation. So, I changed the size very, very  slightly of the cue, which emulates something
7:14:16
that happens in the all but the most expensive  zoom lenses. To iris out, all I need to do is take
7:14:22
a big PNG with a hole punched in the middle, zoom  it way large, and then zoom it in and get smaller.
7:14:35
The twinkle is just an image that spins, then  fades in, then fades out while it's spinning.
7:14:56
It's not so much that I think that this  is necessarily the be all and the end all of making animation, right? It's really not. But  I wanted to point out that this animation style,
7:15:06
which is a style, allows me to modify those  components live in real time as the director
7:15:13
gives me notes in rehearsal. Hey, can  she walk across the stage slower? Hey, can that oak tree be bluer? Hey, can Dopey  actually can we replace Dopey with Doc? Right?
7:15:24
Like all those things can be done really  quickly. What used to require me saying,
7:15:29
I'll take that note and I'll go back to my studio,  re-edit my original, re-render, wait for the
7:15:35
renderer computer to output, and then bring that  file in and see what happens. Not necessary. Now
2D geometry fading
7:15:46
all of these fade cues which  we've been using have been fading
7:15:52
um a single parameter or a pair of parameters  in QLab uh and in much in the same way that we
7:16:00
faded audio effects uh audio parameters.  But we also have the ability in a um in a
7:16:11
uh fade cue to fade geometry parameters of  video cues according to a path rather than
7:16:19
a curve. The path fading is your old friend  now from object audio. So here's a rocket.
7:16:33
I can move that rocket in a circle by using a fade cue set to a  path that fades translation parameters.
7:16:45
It fades the X and Y translation together
7:16:50
in a pair, moving the object, which is in this case  a video cue, around the stage in a circle,
7:17:06
much the same way object audio worked. I made a couple of demos here for  the kinds of different movements that
7:17:15
are possible with these 2D fades. Like  here's a satellite orbiting the Earth.
7:17:24
I wouldn't call it the world's grooviest animation
7:17:30
here. I've got a fade and a start  cue in a group. And I'm using the
7:17:37
um uh oh, if I should have set  that to hard stop and restart.
7:17:49
Here's a snowflake fluttering down.  And here we start to see a possibility.
7:17:56
I've got two different cues going at  once. This one fades the rotation X
7:18:02
and Y in a figure of eight. Meanwhile, this  cue fades the translation down this line. So,
7:18:11
we've got two motions going on simultaneously,  which helps to generate a fairly natural and
7:18:17
not very much computer-y program type  of behavior. This feels really organic
7:18:26
in a way that would be hard to do in  my opinion with single axis fading.
7:18:34
Speaking of old fashioned things,  here's a telephone ringing uh bouncing around the desk as it rings.
7:18:44
It's a series of fades in groups. There's  the ring group which blurs fades in a blur,
7:18:54
moves the phone around in a wild pattern,  rotates the phone around in a wild pattern,
7:19:01
though not very much. And then stopping  it stops that uh stopping the ring stops
7:19:09
that group and then restores the translation and  blur and rotation back to their home parameters.
7:19:20
This one. Um, this one's This one needs work. The  plane flies. That needs work. I'm I'm not proud of
7:19:27
that, but I thought I'd show it to you anyway. Uh,  we also have uh the stereotypical boomerang man,
7:19:35
as we all have heard of before, who shows up,  throws his boomerang, it comes back to him,
7:19:40
and he's gone. That one just shows off uh really  how many different emoji there are. Um the whole
7:19:49
background, these are all text cues for fun. The  whole background is just the white square emoji,
7:19:55
but it's zoomed very large. The boomerang appears  off screen as does Boomerang Man. Then a fade just
7:20:04
brings the Boomerang on stage with Boomerang Man.  And Boomerang Man has his anchor point set to his
7:20:12
left foot. His left. Yeah, his left foot. So  that when he steps down, it pivots around that
7:20:22
foot. When he throws the boomerang, it goes in an  oval while spinning using a single axis rotation.
7:20:33
Then the exclamation mark appears  and then everybody goes away.
7:20:38
I've tried to think of a demo  that would use as many different um switchable settings of the fade cue  as possible. And so that one has I think
7:20:46
every form of fade that's possible in a video  cue. And then we have the uh the hole-in-one
7:20:55
which is just the golf ball circling  around working exactly like a real golf ball obviously does. The zeroing  in is a series of concentric circles
7:21:13
that just gets smaller and smaller  and smaller with the smooth path
7:21:19
checkbox checked so that it stays nice and smooth.
7:21:28
So there we go. Those are some examples of  things you can do with video, ways that you
7:21:34
can animate video within QLab that do not require  you to go to an outside tool, an authoring tool,
7:21:40
and produce media that exactly fits the needs. A  lot of the times when I see projection designers
7:21:46
struggling to use QLab effectively who  feel as though QLab is holding them back,
7:21:52
those very same designers are also sort  of passing on using most of QLab's powers.
7:22:00
They're passing on using QLab's layering or QLab's  translation and animation tools and instead just
7:22:07
basically playing one movie at a time full screen  with all of the work being done in their nonlinear
7:22:13
editor. And if that's what you're used to,  I can understand why that's your tendency. But I'm here to encourage you to consider doing  more in QLab and less in your editor and allowing
7:22:25
you which allows you the flexibility to  sort of play around in the playback tool.
Questions and general video discussion
7:22:32
Okay. Any video questions at all?
7:22:40
Any video folks here? Folks who use QLab  for video or plan to? Yeah. What kind of
7:22:46
context are you working in? You working  in a theater? You working on dance? You working in broadcast? Anyone? Well, I do work  in a theater. I um I work at Hopkins in DC and
7:22:59
We mostly use it for like film screenings  and like stuff. However, what I came here
7:23:05
for is that we have a media that's not to create  a show like a live TV show in our live broadcast.
7:23:17
Magnificent. That sounds great. Do you  feel like you're seeing the kinds of tools you need to use to do that? Yeah.  I didn't know so much to be done in this.
7:23:28
Great. Because you mentioned specifically um  working in a broadcast studio, I do want to
Keying in QLab
7:23:36
uh I did I did pass on an opportunity  to mention that there is a video effect that you will probably care about a great  deal, which is where are you? Where are you?
7:23:50
These the ordering of these is quite logical,  but it's still difficult for me to spot it, what I'm looking for when I'm in a hurry. Linear key.  Linear key is like chroma key, but a little easier
7:24:02
uh to get a nice key in in an adverse situation.  This linear key effect, which can work on either
7:24:08
a green screen or a blue screen, will let you  chroma key uh a video cue in QLab live in real time.
7:24:23
Yeah. So, if you have a camera on you, that camera  comes into QLab and you're on a green background,
7:24:30
this um this video effect linear key will let you  key out your background in that camera cue. I'm
7:24:40
sorry. Yeah, all the camera cue. Um, now what  that, so here we have a sort of a headbendy thing
7:24:50
in a broadcast context when you do a chroma  key, it keys out the green background and
7:24:57
produces what? Black pixels or it produces the  fill layer that you're using to mix in in your
7:25:04
mixer. But in broadcast, there's no such thing as  transparency, right? But in QLab, what does the key
7:25:11
do? It keys out the green in the in the camera  cue and produces transparency. So you can then
7:25:18
layer the camera cue on top of another cue in  QLab and then the end result is a key and a fill.
7:25:29
Oh yeah, for sure. Yeah, I just  No, I never mind. It's a bad idea.
7:25:36
I was gonna I was wondering if I project  the right green and stand in front of it.
Live green-screen experiment (it worked!)
7:25:46
All right, let's see if this works. Uh, text cue. Nothing but text cue. Or it  could just look super weird, right?
7:25:59
Yeah. So, here's a text cue. Okay, we're  going to play it on the QClass stage.
7:26:10
Oh, it's not. Well, I'm gonna shoot. Yeah. Yeah. Yeah.
7:26:26
it holds the better the key.
7:26:32
Yeah, I was thinking Yeah.
7:26:38
So, I don't got that much room.
7:26:45
Yeah. I was hoping that you'd be not in the green.  Yeah. There we go. Yeah. You You come over here.
7:26:50
Okay. There we go. There we go. All right. Oh,  boy. For the camera, we're using the Blackmagic.
7:27:02
It says that the UltraStudio  recorder is disconnected.
7:27:07
There it is. It's a different one. Thank  you. We're going to do a weather report from It's raining. Okay. Right. Yes. No, no,  no. Hang on. I've just I'm just testing the
7:27:19
camera. So the trouble is I don't want this  camera to be playing on that same display,
7:27:25
right? Because that display is meant  to be our green background. So I'm going to send this camera to some  imaginary other display somewhere
7:27:39
and I'm going to look at  that imaginary other display.
7:27:45
Here's the linear key without  any real work done on it.
7:27:54
What's that? Yeah. So,
7:28:04
what did I put you on? What layer I  put you on? Intermediary Syphon. You
7:28:10
go to intermediary Syphon 2. The camera  needs to be on a higher layer. Yep. Good.
7:28:15
And then the thing that I want to fill behind  him is on a lower layer. So we can put uh Oh,
7:28:26
wait. I know. I was hoping you would be the bear.
7:28:40
It's sort of like actually a great key  because it's perfectly evenly grain. It actually is a really good key. Yeah, you're  right. Now, this diagonal line is because Alec
7:28:49
because the table is here, Alec is also seeing  some of the black that's under the the lower
7:28:55
edge. If you zoom in on Chris a little Oh, you  are zoomed all the way in. Physically zoom and
7:29:00
then hold it quite low. Oh, go here. I can  I'll do a selfie. Yeah, you got to un-zoom.
7:29:06
Hold on. Technical difficulties. What's that?  Did I disconnect? Oh, that's Oh, that's a Oh,
7:29:12
it's just doing a I I pressed the playback. You  pressed the playback button on the camera. It's like showing. Okay, now we're seeing I don't know.  We're seeing too much. Oh, lordy. There we go. Now
7:29:25
we're not focused. What's happening? Manual  focus. Manual focus. Okay, autofocus. Okay,
7:29:32
please autofocus on me. Oh no, I got to back  button. Focus it. There we go. There we go. Oh
7:29:38
boy. This is How's your forearms? It's great. It's  fine. Oh, right, right, right. There we go. So, it
7:29:49
works, right? The answer is the linear key pulls  the key pretty nicely on the green background.
7:29:54
This is all you got to do. And but truthfully,  if we had if we were so what if we were rear
7:30:03
projecting onto the psych or if the projector  were at any angle that allowed Chris to stand
7:30:09
somewhere and be in front of the psych without  the green light of the projector hitting him,
7:30:16
we'd have no trouble. Right. So there we go. I  didn't loop the bear. I don't know why. Of course,
7:30:26
the bear itself has green, right? So, if  I linear key out the green of the bear.
7:30:37
And now we can put the Chris and  the bear, you know, somewhere.
7:30:54
Oh, space bear. Space bear. There we go.  Chris and the bear both in space. Yeah.
7:31:03
All on an entry level base Mac Mini. Telling  you. Yeah. This is uh this is cinema gold. Okay.
7:31:19
And Chris got his exercise for the  week. Well, at least until leg day.
How are folks in class using QLab?
7:31:32
What else are folks using QLab for? Broadcast  setting to try to do a live tape show. What
7:31:37
else are folks using QLab for? Theater. Yeah.  Quote unquote the legit theater as they call
7:31:45
it for whatever reason. I think no  legit was meant. Never mind. Yeah. Corporate. What kind of corporate What kind  of corporate shows are you doing with QLab?
7:32:07
Uh,
7:32:15
Yep. Yep. Yep. Yep. Yep. Great. Are  folks finding specifically video,
7:32:25
I guess. Are folks finding that the thing that  they were hoping to figure out how to do is among
7:32:30
the things we discussed tomorrow? Tomorrow, which  is lights. Lights. Yeah, great. Super. All right.
7:32:42
What is a good uh halfhour  topic to go next? I think
7:32:54
Yeah, that wasn't my imagination.  How exciting is the stream kosher?
7:33:05
so far. How exciting.
7:33:17
All right. Um, we've talked about  it a couple of times. Chris has been particularly excited about this topic.
Hardware requirements
7:33:27
No, no, no. It's great. I mean, you have I I meant  what I said. You've been excited about this topic. So I want to talk about hardware requirements  for QLab because this is a question we get a lot
7:33:35
um and it's a question where the answer is kind of  in flux um these days and will be even further in
7:33:41
flux as soon as Tuesday uh depending on what  Apple decides to talk about on Tuesday but I
7:33:47
think it's probably the iPhone in which case  we don't care. I mean we care but not for QLab.
7:33:53
That's it. That's the hard that's the requirements  for QLab. We're done. macOS 11 or newer. Uh,
7:34:01
this is a great opportunity for me to say QLab is  um known to work on macOS 11 through the current
7:34:10
version of macOS. And if you pay attention to  Apple News, you know that um a Apple's changing
7:34:19
their numbering scheme for macOS for all their  operating systems to be a year based number. So,
7:34:26
the next version of macOS to come out, which  is coming out very soon, and it has been in beta all summer, will be macOS 26. We're jumping from  whatever number it's on right now, 16 to 26. Uh,
7:34:42
now a clever person will notice macOS 26 coming  out this month. That's not 2026. Surely 2026 is
7:34:54
next year. But Apple has carefully done us a  service. The number of the OS version is the
7:35:02
last two digits of the year that it ought to be  before you update your Mac. If your Mac is used
7:35:09
for shows, I am begging you not to update  to macOS 26 soon. Begging you. macOS 26
7:35:19
is making a lot of changes to the basic user  interface of Mac. Some folks might like it,
7:35:26
some folks might dislike it. That's not  what's important here. What's important here is it's going to work very differently. And  because this summer has been such a chaotic beta
7:35:36
cycle and every version of the beta of Mac  OS 26 has been in some way truly deficient.
7:35:44
I uh we haven't felt ready to tackle the question  of beta testing QLab on macOS 26 and so we are not
7:35:53
yet 100% confident about how it will look and how  it will run and whether there will be bugs. So I'm
7:35:59
just begging you to wait unless you have no shows  coming up and you're willing to tolerate some
7:36:06
bizarre QLab behavior. But any version of macOS up  until 26 from 11 through 16 good to go. Okay, but
7:36:19
really right that's not enough information. Any  Apple silicon processor is good enough to run QLab.
7:36:27
M1, M2, M3, M4 or any of their suffixes. Right? So  they're the basic naming scheme is M then a number
7:36:37
and then either nothing or the words pro, max  or ultra. An M something or an M something pro,
7:36:46
M something max or M something ultra. All great  for running QLab. 8 GB of RAM is a wonderful
7:36:52
minimum. Because of the LLM hype and because of the  unbelievably bad press that Apple has been getting
7:37:00
about their particular approach, i.e. failed  approach, to the LLM hype, which in my opinion is
7:37:07
actually a perfectly reasonable approach, which  is stay out of it until it settles down. But they've been taking heat for it. So, new Macs all  come with 16 GB of RAM now because you need a lot
7:37:16
of RAM to do LLM stuff. So fortunately for those  of us who are LLM haters as me, uh the LLM hype
7:37:25
has turned the floor for the amount of RAM  into more than I would recommend as the minimum
7:37:33
for QLab. Beautiful. You need an SSD in your Mac  big enough to hold your show. That's about it.
Hardware - video
7:37:42
If you are doing video, you need to worry about  how many external displays your Mac supports.
7:37:48
An M1 or M2 supports two displays with an  asterisk. If it's a laptop or the iMac,
7:37:54
the built-in display is one of those two displays.  An M1 Pro or M3based Mac supports two displays,
7:38:02
and the built-in display on a laptop or iMac  doesn't count towards that limit. The M2 or M I'm
7:38:11
sorry, the M4 or the M2, M3 or M4 Pro all support  three displays plus the built-in. The M1,2 and 3
7:38:21
Max all support four displays. The M1 Ultra and M4  Max support five displays. The M2 Ultra supports
7:38:29
eight 4K displays or siz 6K or three 8K. And the M...  That should be a three. Let's fix that right now.
7:38:46
The M3 Ultra supports eight 6K screens or  four 8K screens, which is truly insane.
7:38:55
And all of that is separate from displays that  use Blackmagic devices or NDI output. If you
7:39:05
have one of these monstrously powerful Macs  and you choose not to use any of the built-in
7:39:11
display support and you just use these, this  the numerical limits is are irrelevant. But
7:39:18
the more powerful Mac has plenty of power to  burn drive to drive these. The exact number of
7:39:25
these that is supported on an individual Mac  is hard to quantify. Most Macs though don't
7:39:30
have enough plugs to plug more of these  in than it can handle. And those that
7:39:36
um because of Thunderbolt is weird, it's difficult  to get more plugs without weird things happening.
7:39:43
But the long and short of it is several.  Let's go with several. Does that feel good?
Hardware - which Mac?
7:39:52
Sam, please just tell me which Mac I should  buy. If you're doing a low intensity show,
7:39:57
quite literally any Mac with Apple Silicon will  be great. If you're just doing walk-in, walk out,
7:40:02
lights up, lights down, very straightforward,  vanilla, find the cheapest Apple Silicon Mac you can from a reputable source. Buy it. Never worry.  Almost certainly if you have a high intensity show
7:40:15
except for video, any Apple Silicon Mac with 16  gigabytes of RAM, don't use an M1 or M2 MacBook
7:40:22
Air. Don't use an M1 or M2 iMac because they  don't have fans, which is cool, but it doesn't
7:40:28
keep them that cool. So, when they work hard, the  temperature rises, when the temperature rises,
7:40:34
the processors clock themselves down so that they  don't overheat. Other than that though, any other
7:40:42
Apple Silicon Mac will outperform even the Intel  Mac Pro. Um, if you're not sure what to do and you
7:40:50
can spend $1,000 on a Mac, buy the entry level  M4 Mac Mini and a couple of these and never
7:41:03
look back if you're doing video. If you're  not doing video, don't bother with these. Just buy this and take yourself out to dinner  for the rest. Audio interfaces. I get asked about
Hardware - audio interfaces
7:41:13
audio interfaces quite a lot. MOTU AV era devices.  Those are the basically any MOTU audio interface
7:41:19
built in the last few years. Really great. Uh RME  is a German manufacturer of audio interfaces. All
7:41:26
of their interfaces are named the something face.  There's the Digiface, the Fireface, the you know,
7:41:31
I don't know, hit me in the face. There's uh all  the RME faces are quite good, but they must be
7:41:37
kept cool. Do not put them in a rack together  with your amplifiers. Keep them cool and they
7:41:42
will last you forever. The Focusrite Sapphire Pro  and Clarett series, the Focusrite Scarlet Gen 2,
7:41:50
which is now like 12 years old. The Gen One is  like 14 years old. You don't even have to think about it anymore. The Gen Two and up, great. I  really, really like them. The Universal Audio Volt
7:42:00
and Apollo. Never laid my hands on them myself,  but I've read their spec sheet and I've read very
7:42:05
good reviews. And Universal Audio in general  is just very reputable. Iconnectivity makes
7:42:11
peculiar but very well-made devices. Highly  recommended. And Dante, of course, is no actual
7:42:18
audio interface needed. So that's my favorite  questions here. Anything to add to this list?
7:42:27
I didn't even bother putting metric halo on this  list. Metric Halo... their cheap interface is
7:42:33
$3,400. It will, on the other hand, outlive all  of us, this building, and all life on Earth, but
7:42:41
$3,400 is a lot of money. Alec? Buy a Dante-  recommended Ethernet dongle if you are in the
7:42:49
market for Ethernet. So, you know, I challenge  on that one. I have said, I... the suggestion. So,
7:43:00
the suggestion from Alec is if you're going to  use Dante, um, most Macs don't have Ethernet ports
7:43:07
built into them physically. The only ones that  do are the Mac Studio, the Mac Pro, and the Mac,
7:43:14
uh, the iMac, if you get the expensive power brick  because the Ethernet port, believe it or not,
7:43:19
lives in the power brick uh, and is connected  to the Mac through the cable that connects the
7:43:25
power brick to the Mac, which is a custom cable.  It's actually kind of a brilliant idea because the power brick lives on the floor under your  desk and that's where the Ethernet comes out of
7:43:33
the wall for a lot of folks. I think it's kind  of ingenious. The Mini does the same thing. No,
7:43:38
the Mini has an Ethernet. Oh, the Mini has  an Ethernet port. Yes, correct. Good. So, the Mini, the Studio, the iMac with the more  expensive power brick and the Pro. The laptops
7:43:50
uh do not have an Ethernet port built in. So, Alex  said, "If you're going to use Dante and you're not
7:43:56
using a built-in Ethernet port, you want to get  a Dante approved Ethernet adapter like this one,
7:44:03
which is made by Anker. Is this on their list?"  Yeah. I have found um the following to be. So,
7:44:13
if you get a good Ethernet adapter, if you get  a quality Ethernet adapter, the only problem
7:44:18
you will have with Dante is getting the warning  that it's not on their approved list. If you get
7:44:23
a crummy Ethernet adapter, it won't work properly  and you'll get the warning. But my feeling is that
7:44:29
their approved list is too stringent because  I've used um I have another Anker Ethernet
7:44:37
adapter other than this one, which I know uses  the same chip as this one, but it's not on their
7:44:43
approved list. So, I get the complaining message,  but no Dante problems. I think this is like based
7:44:51
on which Ethernet driver it uses built into your  Mac. So you probably have one with a different
7:44:56
chip inside of it, but it's still probably  fine. You're right. That's interesting. Well, I'll learn more about it hopefully. I'm a little  skeptical and I've become a little skeptical of
7:45:05
Agnate. They're starting to make the move that  Dropbox made when they went from being a piece of software designed for people to use and get their  work done to a piece of software designed to make
7:45:14
Dropbox as much money as possible. Um, which is  not something I fundamentally begrudge companies
7:45:19
for doing, but it's a little vexing to watch Dante  go from making your show as easy as possible is
7:45:25
our main goal to making your show as easy as  possible is good and selling licenses to large
7:45:31
corporate deployments is also good. It's not quite  as confidence inspiring for me personally. Um,
7:45:40
that said, everyone's got to make a living  and finances are complicated. So, I'm not like
7:45:47
angry about it. I'm just a little hesitant and  a little skeptical of the like approved list and
7:45:53
what the motivations behind that are. Are they all  technical or are they a little bit sociopolitical?
7:46:00
Speaking of being skeptical, bad audio interfaces.  Um, these are audio interfaces which aren't so
7:46:07
much bad as audio interfaces which have definitely  been the source of many support questions to us.
7:46:13
uh things made by PreSonus, things made by M-Audio,  things made by Behringer, Tascam, or Avid.
7:46:21
I want to specifically point out that when I say I  have a problem with Avid's devices, it is because
7:46:26
Avid's devices are made first and foremost to  work well with Avid software, which they do. They
7:46:32
are well-made devices that do good work with Avid  software. Avid's support of other software using
7:46:38
their devices is middling. So, it's not so much  a problem problem as it is your mileage may vary
7:46:44
and it may be difficult to get support. Anything  without balanced outputs is not recommended in
7:46:50
my opinion. This is the distance you should  trust an unbalanced audio signal to travel
7:46:58
unless you are a very tall person  in which case this is the distance.
Hardware - USB-C
7:47:07
Okay, this is a thing. Once upon a time, there was  USB and it was pretty cool because it was better
7:47:17
than what it replaced. And it came in the plugs  came in two flavors. There was the USB-A plug,
7:47:24
which was like this, and the USB-B plug,  which was like this. And you could tell
7:47:30
you were plugging the right end into the right  end because they would not fit the other way.
7:47:35
This was on your Mac. This was on your  printer. Okay, great. But the C in the USB,
7:47:46
the USB in the USB-C connector does not mean  USB, the language computers speak to printers
7:47:53
with. It just means that this connector, the  USB-C connector, was devised and adopted by the
7:48:02
USB standards body as the next connector  that USB was going to use. But the same
7:48:08
connector is also used for other things that have  nothing to do with USB, most notably Thunderbolt.
7:48:18
The USB-C connector is the connector of choice  for Thunderbolt 2 and newer. Yeah, Thunderbolt
7:48:27
3 and newer. Yeah, Thunderbolt 3 and newer. Not  going to talk about what Thunderbolt 1 and 2
7:48:33
used. It's complicated. Thunderbolt was a clever  idea that some folks at Intel had where they took
7:48:41
the PCIe bus, which I'll explain what that is  in a second, the DisplayPort bus, and power
7:48:48
delivery mechanism and bundled it together in one  cable. And then for that one cable, they thought,
7:48:54
okay, the USB-C connector is a nice connector to  use for that cable. And they're right. PCIe is
7:49:02
the communications bus that is used in a computer  when you put you have a big desktop tower computer
7:49:09
and you put a card in it and that card's got  a connector that's like a zillion little gold fingers. They go into a big wide slot. That slot  is a PCIe slot and it connects directly to the CPU
7:49:23
of the computer with a very very fast connection.  The CPU of the computer natively understands PCIe
7:49:30
as the way I talk to other stuff. If you have an  Ethernet connection built into your old desktop
7:49:37
PC, what's probably going on is that the Ethernet  connection is secretly a little PCI card that's
7:49:42
just not in card form, and it connects directly to  the CPU with PCIe as well. I don't know if that's
7:49:49
most likely, but it is likely. The good thing  about PCIe is it's very, very fast and not that
7:49:56
expensive. The bad thing about PCIe is it only  works over about that distance. Until these clever
7:50:02
folks figured out a way to make it work over about  that distance. And then they thought, okay, great. Now PCIe devices can move outside of the computer.  The computer can be smaller because we don't need
7:50:12
all the space for all those cards. And the thing  out there could be not in card form. So you could
7:50:20
have say a video capture card that is a little box  with a Thunderbolt cable plugs into the computer
7:50:28
and it connects as though it's a PCIe card in the  slot of the card of the chassis of the computer
7:50:35
and it'll be real fast and real groovy. Okay,  phenomenal. Turns out the electrical properties
7:50:42
of the USB-C connector and the USB-C cable are  stupendous and ideal for something like that.
7:50:49
So we use the USB-C connector for Thunderbolt.  Thunderbolt is PCIe. It's also DisplayPort
7:50:56
which is this connector which looks like HDMI  but asymmetrical and slightly larger. It also
7:51:06
looks more delicate than HDMI but that is a a  lie. It is dramatically less delicate than HDMI.
7:51:13
If you go and yank on a Thunderbolt, on a DisplayPort  cable, it will not pop out of the socket because it's got these goofy little teeth that  keep it in. Whereas, if you go and take the same
7:51:23
amount of force and yank on an HDMI cable, even  odds, it either unplugs or pulls the device off
7:51:29
the desk or pulls the cable out of the socket  and you just are left with a zillion little gold
7:51:37
fingers sticking out and you've ripped the  cable out of the plug. You need to pull the plug out and then either re-solder it if you're  some kind of self-punishing person or throw it
7:51:48
away and get a new one. DisplayPort is also the  lingua franca of video signals inside a computer.
7:51:59
the GPU in the computer, the graphics processing  unit, when it makes video and it's like, "Okay,
7:52:05
this video is ready to go to a screen, it  sends that signal to the screen in DisplayPort
7:52:10
language. If that DisplayPort language wants  to exit the computer and go on a cable, it could
7:52:17
come to an HDMI connector, get translated to HDMI  language, go over the HDMI cable into the projec...
7:52:26
socket on the side of your computer, and then  that that conversation happens in DisplayPort language. Thunderbolt supports DisplayPort  inside that same wire. So, you plug USB-C
7:52:38
connector into your Mac, USB-C connector into your  screen. The screen hollers down the cable, "Hey,
7:52:43
I'm a screen." And the Mac is like, "That's dope.  I can make this port be a DisplayPort even though
7:52:49
it's actually a USB-C socket. I'm not a barge."  Not a barge. Not a barge. Okay, good for you.
7:52:55
It's going to be, it's going to be okay. And you're  going to get pixels and it's going to be lovely. PD, power delivery, is a method where uh you  know how you plug your phone into any USB socket
7:53:07
on the planet and it charges. That's because  the base design of USB includes some stupid,
7:53:14
deliberately stupid charging circuitry. Okay? And  that's phenomenal, right? Because that's how you
7:53:20
charge your phone anywhere in any USB socket.  Power delivery is like, let's take that, make
7:53:25
it 5% less stupid so that we can charge devices  that need different amounts of power. So my laptop
7:53:33
wants 140 watts of power if it can take it. And so  it has a little bit of cleverness. When you plug
7:53:40
in a power cable, a USB-C cable, it hollers down.  I'm not a barge and I want 140 watts. And if the
7:53:49
power supply on the other side knows what to do  with that signal, it supplies up to 140 watts of
7:53:54
power. But the really smart thing is that if the  power supply doesn't know what that message means, it just continues to supply the five milliamps or I  can't remember how much the base wattage of USB
7:54:07
is. The very very small trickle charge 500 milliamps,  right? It supplies 500 milliamps,
7:54:15
no problem, and then trickle charges the Mac very  slowly. Yeah. So, that's power delivery. Really
7:54:22
clever. So, we bundled three kinds of things that  people really super duper want and use all the
7:54:27
time into one skinny little cable. And we gave it  a really convenient connector that is physically
7:54:33
robust, impossible to plug in upside down,  and puts the bit that wears out in the cable,
7:54:41
not on the connector built into the Mac. So,  when your USB-C connector starts to get flaky,
7:54:49
the the part that has worn out is the part in the  cable. You can ditch the cable, get a new cable, plug it in, and it will feel brand new again.  Groovy, brilliant. Everyone's happy. And then the
7:55:02
USB folks came along and said, "Well, we're going  to use the USB-C connector also, and we're going to
7:55:08
use it for USB 2, USB 3, USB 3.1, USB 3.2, and USB  4." A normal human person might imagine that those
7:55:17
are five versions of one language, USB. And there  you would be tragically wrong. When you plug in
7:55:27
a USB 2 device to a computer, a modern computer,  that computer's like, "Oh, I've got to speak USB
7:55:33
2 now. I look up my USB 2 dictionary." It's a  whole different story. USB 3, 3.1, and 3.2 seem
7:55:40
like they're minor revisions. They're in fact  completely different. USB 4 is basically just
7:55:45
Thunderbolt, but you're allowed to not be as fast  as possible. It's madness. Some of the pins on the
7:55:54
USB-C connection are optional. I don't know why.  The real reason is if I'm using a USB 2 connection
7:56:02
over a like this Go Box has USB-C sockets, but  it's very very little data that passes across this
7:56:09
thing. So, it speaks USB 2. If I plug in a USB  cable, a USB-C cable that has only six of the 24
7:56:17
pins connected, it will work. But if I try to plug  in this Thunderbolt device with only six pins,
7:56:26
it will not work. I believe that 12 of the 24  pins are necessary to make this thing work, but
7:56:31
I'm not 100% certain. Cables which are marketed  and branded as being full featured USB-C cables have
7:56:41
every pin connected. If you are not sure if your  cable is full featured, you can use a cable tester.
7:56:51
Are these cable testers very easy to come by, you  ask? No. No, they are not. Here's one. It looks
7:56:58
like a homemade project because it is a homemade  project. Not by me, by caberqu.com.
7:57:07
This person 3D prints this little thing. Has  these little circuit boards made. I got to put it together with a screwdriver myself. It was  really fun. When you plug in a Thunderbolt,
7:57:19
well, when you plug in any cable that  has USB-C connectors on it to this tester,
7:57:29
it will light up a bunch of lights and the lights  that are lit up will demonstrate whether it is a
7:57:35
full featured cable or not. There is a fluke in my  particular copy of this tester. That means that
7:57:43
certain lights don't light up when they ought to.  That's because I bought a very early copy of one
7:57:48
cuz I was excited to try it out. But in short, the  full featured cable should light up all the lights
7:57:56
on a tester like this. If you don't want to spend  time wondering whether you've got the right cable
7:58:01
for the right USB-C connector device, just throw  out all the ones that don't have all the pins
7:58:06
connected because there's no reason not to use  them except maybe the one that you use to charge your phone cuz it's super thin and bendy and  charging your phone doesn't need all the pins. So,
7:58:20
USB-C Ethernet adapters, as Alec was talking  about, some of them are you some of them use
7:58:29
the PCIe bus to connect very high at very  high speed to the CPU of your computer and
7:58:35
those are impressively fast. Some of them  use USB which is an intermediary step and
7:58:43
some of those might not work as well as the  others. So, when you buy a Ethernet adapter,
7:58:49
what does it say in the marketing literature?  A USB-C to Ethernet adapter. Well, yes, I know it's a USB-C to Ethernet adapter  physically, but is it USB-C that uses USB
7:58:59
or is it USB-C that uses Thunderbolt? Nobody  knows. Nobody knows. What do you have to do?
7:59:06
You have to find out what Ethernet chip is inside  here and then find out whether that Ethernet chip
7:59:12
wants to use Thunderbolt or USB to connect to  the Mac. It is crazy making. Or you could just
7:59:17
let Audinate do the homework for you and only buy  one that are ones that are recommended by Audinate.
7:59:25
Video can be connected via a USB-C connector  because display port is a technology that uses
7:59:33
that is part of Thunderbolt. But also you  can connect monitors to computers using a
7:59:39
USB connection, not USB-C, USB, using a technology  called DisplayLink, which requires you to install
7:59:45
a software driver on your Mac, which converts  video signals to USB and connects to low quality
7:59:52
displays that way. DisplayLink is flaky as heck.  Don't use it. If you have to get a video adapter
7:59:59
and that video adapter says, "To make this work,  install software, throw it away, get your money back. Do not do not do not be like this guy who  learned about DisplayLink in front of an audience
8:00:11
of many hundreds. Many hundreds, in a beloved  annual traditional show that had been happening
8:00:19
for decades. And this year they hired me to do  some video and never mind. Uggh is how I felt.
8:00:26
Ugg is how I feel now. USB4 is Thunderbolt 4. The  only difference between them is a Thunderbolt 4
8:00:35
device must operate at full speed. A USB4 device  is permitted to limp along at partial speed.
8:00:43
USB4 version 2 sort of equals Thunderbolt 5. And I  ask you of what value is almost equal? All I can
8:00:52
say is look for the little lightning bolt. That  means Thunderbolt. It is more expensive. What you
8:01:01
get for that more expensive is it always works.  If you see the little Solara cactus, that is USB.
8:01:10
That is fine for your mouse, keyboard, printer,  whatever. Low intensity stuff and probably fine for
8:01:15
your audio interface most of the time. But some  of the time it's a flimsy Ethernet driver that
8:01:22
doesn't work properly and doesn't pass Dante.  Some of the time it's a lousy video translator
8:01:27
that requires you to install drivers that don't  work. It is challenging to understand. So my
8:01:32
parting words for the day are USB-C is very cool,  very useful, occasionally challenging. Proceed
8:01:41
with caution. There any questions? Yeah. Any  pitfalls to be aware of? Like I have a M4 Max
8:01:55
So, I think according to your display, I could do  up to five displays. Yeah, you're sitting pretty
8:02:01
great. But like, how do I get five displays out  of three Thunderbolt five ports and not worry
8:02:06
about? You get a proper actual Thunderbolt  USB-C to DisplayPort cable. Thunderbolt 5 can
8:02:16
daisy chain. Thunderbolt 4 can daisy chain, but  the way that the DisplayPort bus daisy chains itself can be a little odd. Um, Sonnet makes an  uh a set of adapters that connect with USB-C
8:02:29
to your Mac and provide two HDMI or two DisplayPort  sockets. Love those. Always work. Is it worth in
8:02:38
that context like video context to get make sure  I'm buying like a Thunderbolt 5 product and not
8:02:43
a USB product? Thunderbolt four or five? Yeah.  Yes, it is always for video always. Can I do I
8:02:50
have to work like should I prioritize like  let's make sure I have a couple coming out of this port on this side and a couple coming  out of this port on this side because like a
8:02:58
port might have a limit or is it like if I can  get that device that you described that's going to split out a bunch of displays into one port  that's fine that'll work. On the M4 laptops it
8:03:08
doesn't matter on the M1 and M2 laptops. There  were a few models where like this side was one
8:03:15
bus and this side was the other bus. Now, this is  an M4 Max as well. Each of these three USB-C ports
8:03:21
is its own independent Thunderbolt bus. And any  of them can do all any of them can do all. So,
8:03:28
I put two displays here, one display there, one  display there. And never think about it. Yeah.
8:03:37
Thunderbolt two HDMI display  adapters. And on the same page, right next to them is the display link  adapter, which you should not trust. Yeah.
8:03:54
Sonnet products. Where is it?  Thunderbolt products. Display adapters.
8:04:07
Thunderbolt Dual 4K DisplayPort. Great.  Thunderbolt Dual 4K HDMI. Terrific.
8:04:13
USB-C DisplayLink Dual 4K. Garbage. No one  should ever buy under any circumstances.
8:04:19
USB3 DisplayLink Dual. Nope. Goodbye.  USB3 DisplayLink. Nope. Sorry. Goodbye.
8:04:26
Use the ones that are light gray  on the top and black on the face, not the ones that are black all over.  It's like 200 bucks. I think 100 bucks.
8:04:42
the the um I'm sure the display port  one is slightly more expensive. No, slightly cheaper. $80! Poof, and it's a locking  connector that doesn't break. So, hey,
Wrap-up for today and the plan for tomorrow
8:04:54
tomorrow, my friends, is another day. And on that  day, we will talk of lighting and we will talk of
8:05:01
collaboration and we will talk about a bunch of  workflow features built into QLab that are there
8:05:07
just not for the audience but for you to help  make it easy for you to work your way through
8:05:13
making cues, dealing with cues, and running cues.  And Eleanor is very excited about the end of the
8:05:20
day. So, tomorrow lighting workflow collaboration  fun stuff. Hi. And the children's museum for those
8:05:29
who are interested. Um, thank you so much.  Thank you stream folks and I'll see you tomorrow.
