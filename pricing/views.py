from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

@login_required
def checkout(request, plan):
    if request.method == "POST":
        profile = request.user.userprofile
        profile.plan = plan
        profile.save()
        messages.success(request, f"{plan.capitalize()} plan activated!")
        return redirect("/accounts/dashboard/")

    return render(request, "checkout.html", {"plan": plan})
